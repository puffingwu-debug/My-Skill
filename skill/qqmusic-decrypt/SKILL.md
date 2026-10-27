---
name: qqmusic-decrypt
description: 在 macOS 上解密本地 QQ 音乐 musicex V1 加密歌曲（MFLAC、MGG），转换为 MP3 或保留原始音频，支持文件夹批量处理和完整性校验。用于 QQ 音乐解密、破解本地加密音乐或转 MP3；不处理旧版 QMC 和其他平台格式。
---

# QQ 音乐解密与转换

将用户指定的本地 QQ 音乐文件解密为可播放音频。默认输出 320 kbps MP3；用户要无损时选择 `original`，两者都要时选择 `both`。保留原文件和已有输出。

## 执行

1. 确定输入路径。有路径就直接处理；没有路径时先查找 QQ 音乐默认目录 `~/Library/Containers/com.tencent.QQMusicMac/Data/Library/Application Support/QQMusicMac/iQmc`，仅列出候选，未获得批量范围时不要转换整个曲库。
2. 使用随技能提供的脚本，替换下例中的路径占位符。`--inspect` 只读文件信息，不访问登录状态或网络。

```bash
python3 ~/.codex/skills/qqmusic-decrypt/scripts/qqmusic_decrypt.py "/绝对路径/歌曲.mflac" --inspect
python3 ~/.codex/skills/qqmusic-decrypt/scripts/qqmusic_decrypt.py "/绝对路径/歌曲.mflac" --output-dir "/绝对路径/输出目录" --format mp3
```

批量处理时传入文件夹；默认只处理该层的 `.mflac` 和 `.mgg`，只有用户包含子文件夹时才加 `--recursive`。也可传入多个文件。

```bash
python3 ~/.codex/skills/qqmusic-decrypt/scripts/qqmusic_decrypt.py "/绝对路径/歌曲文件夹" --output-dir "/绝对路径/输出目录" --format both
```

3. 根据每首歌的 JSON 结果报告状态与可点击的输出文件链接。任意歌曲失败时脚本返回非零退出码，成功的歌曲仍会保留；不要把整批描述为成功。

## 依赖和边界

- Python 3.10+ 标准库和 `ffmpeg`，无需下载第三方解密程序或安装 Python 包。缺少 FFmpeg 时说明需要安装，再按当前任务授权处理依赖。
- 从本机 QQ 音乐偏好文件读取已有登录状态，仅向 QQ 音乐的 `https://u.y.qq.com/cgi-bin/musicu.fcg` 请求该歌曲的密钥。音频不上传；不记录账号、登录凭据、密钥或完整接口响应。
- 已在 Apple Silicon、QQ 音乐 `11.10.0 (73282)` 和真实 MFLAC 文件上验证。MGG 使用同一解密流程，但没有真实 MGG 回归样本；输出必须通过整首解码校验才能称成功。不承诺其他客户端版本兼容。
- 以实际 `musicex` V1 尾部判断格式，不能只改扩展名。旧 QMC、QTag、STag 直接报告不支持。
- 登录信息缺失、接口拒绝或未返回密钥时，给出脚本显示的原因和原始状态码；可请用户重新登录后再试一次。不重复轰炸接口，不伪造权限或修改客户端。
- 不将账户状态、歌曲密钥、用户音频打包进技能。不静默更改 QQ 音乐、系统安全或网络设置。

## 校验

脚本检查解密后文件头、整首音频解码、FLAC 样本数量与内嵌 MD5（存在时），以及 MP3 全曲解码。只有源 FLAC 完整采样与 MD5 都吻合时，才允许尝试去掉至多 16 字节的非音频尾部，每个候选必须重新通过全部校验。不能无条件截尾或吞掉解码错误。

`flac_md5_verified: false` 表示原 FLAC 未提供 MD5，只有严格解码与样本数通过，不要声称进行了 MD5 校验。MP3 是有损转换，源 PCM 的 MD5 不能用于验证 MP3 与原音频相同。

协议来源、验证记录和开发校验方法见 [references/implementation.md](references/implementation.md)。
