# 实现依据与验证

## 协议依据

- [ownlight6/qmc-decoder](https://github.com/ownlight6/qmc-decoder)，GPL-3.0；`src/ekey_fetch.rs` 的 macOS 偏好文件解析、musicex V1 布局与 QQ 音乐接口请求，`src/qmc2.rs` 的 QMC2 密钥推导、Map/RC4 流程与已知答案。本技能脚本对这些协议逻辑作了 Python 适配，按 GPL-3.0-or-later 提供，许可见技能目录 `LICENSE`。
- [jeff-0717/qq-music-decoder](https://github.com/jeff-0717/qq-music-decoder)，用于交叉核对 Python TEA 和 RC4 算法；不调用其中 Windows 进程内存读取、密钥缓存或元数据网络功能。

musicex 尾部：末尾 8 字节 `musicex\0`；其前为 4 字节小端版本、4 字节小端总尾部大小。总尾部大小包含 16 字节 trailer。从总尾部起始偏移 `0x0C` 的 60 字节为 UTF-16LE media MID；偏移 `0x48` 的 68 字节为 UTF-16LE 资源文件名。文件本身不提供 ekey。

现有登录状态位于 QQ 音乐偏好文件的 `AutoLoginUserInfo`，它是内嵌 NSKeyedArchiver plist。只解析 `strUserAccount` / `nCurrUseId` 和 `strAuthst`。只向 QQ 音乐原域名 POST 请求，禁止携带凭据重定向；不将这些字段写入报告。服务端没有返回密钥时停止当前歌曲。

## 真实样本基线

2026-10-27，Apple Silicon Mac，QQ 音乐 `11.10.0 (73282)`：

- 输入 `kitt-We Never.mflac`，17,473,886 字节，musicex V1。
- 源文件 SHA-256：`a361346f63112815b7b8aac710b40e58406f2c7c7572f20e8b98d2d4e9fb8e2f`。
- 解密后 FLAC：44,100 Hz、16 bit、双声道，7,141,253 个采样帧。
- 解码 PCM MD5 与 FLAC STREAMINFO 一致：`8fedf1a215efb121f2232abf70eecdaf`。
- 初始输出有 6 字节非音频尾部。去掉后，整首严格解码和相同样本数、MD5 全部通过。
- MP3：320,000 bit/s；整首严格解码无错误。不要用 MP3 容器时长的细小差异断言音频截断，应考虑编码延迟和填充。

这只是已验证的样本，不能推导所有文件固定裁掉 6 或 16 字节。客户端内部接口可能变更，其他客户端版本和真实 MGG 尚未验证。

## 开发校验

```bash
python3 -m py_compile scripts/qmc_crypto.py scripts/qqmusic_decrypt.py scripts/test_qqmusic_decrypt.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

真实端到端测试另选一个空输出目录，使用原 MFLAC 执行 `--format both`。报告必须显示源文件未变、全曲解码通过、FLAC MD5 校验通过；再次执行应拒绝覆盖已有结果。
