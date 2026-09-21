//! Human-readable process output only. NEVER use these fallbacks to recover paths,
//! JSON, Git status, or any other machine-readable data that can drive an action.
use encoding_rs::{Decoder, Encoding, CoderResult, UTF_8, UTF_16LE, UTF_16BE, GBK, GB18030};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize)]
pub enum OutputEncoding {
    #[default]
    #[serde(rename = "auto")]
    Auto,
    #[serde(rename = "utf-8")]
    Utf8,
    #[serde(rename = "gbk")]
    Gbk,
    #[serde(rename = "gb18030")]
    Gb18030,
    #[serde(rename = "system")]
    System,
}

fn system_encoding() -> &'static Encoding {
    #[cfg(windows)] {
        // This only reads the current code page. It does not change the console,
        // registry, process locale, JVM file.encoding, or any source file.
        let cp = unsafe { windows::Win32::Globalization::GetACP() };
        return encoding_for_code_page(cp);
    }
    #[cfg(not(windows))] { UTF_8 }
}
#[cfg(any(windows, test))]
fn encoding_for_code_page(cp: u32) -> &'static Encoding {
    match cp {
        65001 => UTF_8,
        936 => GBK,
        54936 => GB18030,
        950 => encoding_rs::BIG5,
        932 => encoding_rs::SHIFT_JIS,
        949 => encoding_rs::EUC_KR,
        874 => encoding_rs::WINDOWS_874,
        866 => encoding_rs::IBM866,
        1250..=1258 => Encoding::for_label(format!("windows-{cp}").as_bytes()).unwrap_or(UTF_8),
        _ => UTF_8,
    }
}

pub struct Decoded {
    pub text: String,
    pub replacements: bool,
    pub encoding: &'static str,
}
impl Decoded {
    fn empty() -> Self { Self { text: String::new(), replacements: false, encoding: "UTF-8" } }
}

/// A per-stream decoder. The small undecided prefix is bounded (at most three
/// UTF-8/BOM bytes); the active decoder preserves multibyte characters across reads.
/// Auto is deliberately a display heuristic, not a trustworthy charset detector.
pub struct TextDecoder {
    decoder: Option<Decoder>,
    fallback: &'static Encoding,
    pending: Vec<u8>,
    at_start: bool,
}
impl TextDecoder {
    pub fn new(policy: OutputEncoding) -> Self { Self::with_system(policy, system_encoding()) }
    fn with_system(policy: OutputEncoding, system: &'static Encoding) -> Self {
        let explicit = match policy {
            OutputEncoding::Auto => None,
            OutputEncoding::Utf8 => Some(UTF_8),
            OutputEncoding::Gbk => Some(GBK),
            OutputEncoding::Gb18030 => Some(GB18030),
            OutputEncoding::System => Some(system),
        };
        Self { decoder: explicit.map(|e| e.new_decoder_with_bom_removal()), fallback: system, pending: Vec::new(), at_start: true }
    }
    fn activate(&mut self, enc: &'static Encoding, remove_bom: bool) {
        self.decoder = Some(if remove_bom { enc.new_decoder_with_bom_removal() } else { enc.new_decoder_without_bom_handling() });
    }
    pub fn push(&mut self, bytes: &[u8], last: bool) -> Decoded {
        if self.decoder.is_some() { return self.decode(bytes, last); }
        let mut input = std::mem::take(&mut self.pending);
        input.extend_from_slice(bytes);
        if input.is_empty() { return Decoded::empty(); }
        let start = self.at_start;
        if start {
            // Handle a BOM even when it arrives in separate pipe reads.
            if input.starts_with(&[0xff, 0xfe]) { self.activate(UTF_16LE, true); }
            else if input.starts_with(&[0xfe, 0xff]) { self.activate(UTF_16BE, true); }
            else if input.starts_with(&[0xef, 0xbb, 0xbf]) { self.activate(UTF_8, true); }
            else if !last && [&[0xff, 0xfe][..], &[0xfe, 0xff][..], &[0xef, 0xbb, 0xbf][..]].iter().any(|bom| bom.starts_with(&input)) {
                self.pending = input; return Decoded::empty();
            }
            self.at_start = false;
            if self.decoder.is_some() { return self.decode(&input, last); }
        }
        match std::str::from_utf8(&input) {
            Ok(text) if text.is_ascii() => Decoded { text: text.into(), ..Decoded::empty() },
            Ok(_) => { self.activate(UTF_8, false); self.decode(&input, last) },
            Err(e) if e.error_len().is_none() && !last => {
                let prefix = &input[..e.valid_up_to()];
                if prefix.is_ascii() {
                    let text = std::str::from_utf8(prefix).expect("validated UTF-8 prefix").to_owned();
                    self.pending.extend_from_slice(&input[e.valid_up_to()..]);
                    Decoded { text, ..Decoded::empty() }
                } else { self.activate(UTF_8, false); self.decode(&input, false) }
            },
            Err(_) => { self.activate(self.fallback, false); self.decode(&input, last) },
        }
    }
    fn decode(&mut self, mut input: &[u8], last: bool) -> Decoded {
        let decoder = self.decoder.as_mut().expect("active decoder");
        let mut result = Decoded { text: String::new(), replacements: false, encoding: decoder.encoding().name() };
        let mut out = [0u8; 8192];
        loop {
            let (status, read, written, errors) = decoder.decode_to_utf8(input, &mut out, last);
            result.text.push_str(std::str::from_utf8(&out[..written]).expect("encoding_rs returns valid UTF-8"));
            result.replacements |= errors;
            input = &input[read..];
            if status == CoderResult::InputEmpty { break; }
        }
        result
    }
}

pub fn display(bytes: &[u8], policy: OutputEncoding) -> Decoded { TextDecoder::new(policy).push(bytes, true) }
pub fn warning(encoding: &str) -> String {
    format!("日志中有无法按 {encoding} 解码的字节，已用替换字符显示；这只影响日志显示。构建结果仍按实际退出码判断。可在运行配置中调整日志编码。")
}

#[cfg(test)]
mod tests {
    use super::*;
    fn streamed(bytes: &[u8], policy: OutputEncoding, system: &'static Encoding, step: usize) -> (String, bool) {
        let mut d = TextDecoder::with_system(policy, system);
        let mut text = String::new(); let mut replaced = false;
        for chunk in bytes.chunks(step) {
            let p = d.push(chunk, false); text.push_str(&p.text); replaced |= p.replacements;
            assert!(d.pending.len() <= 3);
        }
        let p = d.push(&[], true); text.push_str(&p.text); replaced |= p.replacements;
        (text, replaced)
    }
    #[test] fn utf8_all_read_boundaries() {
        let s = "[INFO] 开始构建：源码/PMS 🌸\n日志末尾没有换行";
        for n in 1..=16 { assert_eq!(streamed(s.as_bytes(), OutputEncoding::Auto, GBK, n), (s.into(), false)); }
    }
    #[test] fn gbk_system936_all_read_boundaries() {
        let s = "[INFO] 开始构建：D:\\项目\\源码\\PMS\r\n编译完成，正在启动";
        let (bytes, _, errors) = GBK.encode(s); assert!(!errors);
        assert!(std::str::from_utf8(&bytes).is_err());
        for n in 1..=16 { assert_eq!(streamed(&bytes, OutputEncoding::Auto, encoding_for_code_page(936), n), (s.into(), false)); }
    }
    #[test] fn explicit_gbk_on_utf8_system() {
        let s = "中文错误：找不到符号"; let (b, _, _) = GBK.encode(s);
        for n in 1..=8 { assert_eq!(streamed(&b, OutputEncoding::Gbk, UTF_8, n), (s.into(), false)); }
    }
    #[test] fn gb18030_supplementary_characters() {
        let s = "服务启动🌸"; let (b, _, errors) = GB18030.encode(s); assert!(!errors);
        assert_eq!(streamed(&b, OutputEncoding::Gb18030, UTF_8, 1), (s.into(), false));
    }
    #[test] fn bom_all_read_boundaries() {
        let s = "中文 UTF16 测试 🌸";
        let mut b = vec![0xff, 0xfe]; for c in s.encode_utf16() { b.extend(c.to_le_bytes()); }
        for n in 1..=7 { assert_eq!(streamed(&b, OutputEncoding::Auto, GBK, n), (s.into(), false)); }
        let mut b = vec![0xef, 0xbb, 0xbf]; b.extend(s.as_bytes());
        assert_eq!(streamed(&b, OutputEncoding::Auto, GBK, 1), (s.into(), false));
    }
    #[test] fn ascii_is_not_buffered() {
        let mut d = TextDecoder::with_system(OutputEncoding::Auto, GBK);
        assert_eq!(d.push(b"progress 10%", false).text, "progress 10%");
        let (b, _, _) = GBK.encode("中文"); assert_eq!(d.push(&b, true).text, "中文");
    }
    #[test] fn malformed_and_incomplete_logs_do_not_fail() {
        let (text, replaced) = streamed(b"prefix \xf0\x9f", OutputEncoding::Utf8, UTF_8, 1);
        assert!(replaced); assert!(text.starts_with("prefix "));
        let p = display(b"exit 1 \xff", OutputEncoding::Utf8); assert!(p.replacements);
    }
    #[test] fn large_output_is_not_dropped() {
        let text = "构建日志".repeat(20000); let (b, _, _) = GBK.encode(&text);
        assert_eq!(display(&b, OutputEncoding::Gbk).text, text);
    }
}
