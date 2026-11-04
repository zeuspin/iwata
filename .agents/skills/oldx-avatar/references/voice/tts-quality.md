# TTS 音质、MiniMax 与外部配音交接

在用户指定其他 TTS、反馈句尾电子音／底噪、换声音样本，或使用项目 `.env` 时读本页。用户没有指定其他 TTS 时，默认使用 MiniMax 2.8 HD（`speech-2.8-hd`）；先读 [文本预处理](text-preparation.md)，再按本页 API 和交接契约执行。Qwen 为可选路线，见 [guide.md](guide.md)。选择和参数来自用户本次要求；不要把某个用户接受的声音变成所有项目的默认音色。

## 实测边界与排查顺序

| 观察 | 下一步 | 不能据此断言 |
|---|---|---|
| 样本时长正常，接口报 `Audio.AudioSilentError` | 用 ffmpeg 检查音量；接近静音则请用户重录 | 时长合格就有有效人声 |
| 两份样本合成后用户都听到句尾电子音 | 用同一短文对比无标签版本或另一引擎 | 一定是样本问题，或一定是情绪标签导致 |
| MiniMax 复刻版有杂音 | 保留旧版，用 `need_noise_reduction=true` 新建复刻音色，朗读同一短文比较 | 开启降噪必然无杂音、不会损伤音色 |
| ASR 文字相似度为 1.000 | 只报告文字核对通过，仍需用户听音色、句尾和底噪 | 音质、自然度或声音相似度通过 |
| 分段提示逐词时间错位 | 核对音频指纹、时长、trim_start，按脚本重跑对齐 | 可以提高错位阈值或手改词时间来绕过 |

可用本地检查（不改动音频）：

```powershell
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,duration -of json "sample.m4a"
ffmpeg -hide_banner -i "sample.m4a" -af volumedetect -vn -sn -dn -f null NUL
```

实测：一份 13.5 秒 M4A 的平均音量约 -91 dB，被百炼判为静音；更换有有效人声的录音后成功。这是案例，不能把 -91 dB 当通用语音阈值。峰值到 0 dB 也不能单凭统计认定整段削波。

## 项目 .env

用户明确指定项目 `.env` 时可以由程序读取；这是授权的密钥来源，不是搜索聊天、日志或其他配置。现有技能脚本**不会自动加载 dotenv**，需要调用方先加载到当前子进程环境。

- 允许的密钥名：`DASHSCOPE_API_KEY`、`RUNNINGHUB_API_KEY`、`MINIMAX_API_KEY`。
- 将文件作为数据解析：UTF-8／UTF-8 BOM、忽略注释和空行、按第一个 `=` 分隔、去掉成对外层引号。不执行文件内容，不进行 shell 展开；不把密钥插入命令文本。
- 只报告变量存在且非空，不输出值；API 请求头在进程内构造。不要把 `.env` 复制进 skill、测试、产物或提交记录。
- `.gitignore` 忽略 `.env`、`.env.*`；可以保留不含真实值的 `.env.example`。
- MiniMax 合成使用自己的 Key，现有 `align_words.py` 仍调用百炼，视频使用 RunningHub；换 TTS 不代表不再需要百炼 Key。

## MiniMax：先试听，再全文

当前已有脚本没有 MiniMax 命令或 `--provider` 参数。使用下面的官方 API 交互，不要直接把 `common.py` 中的 Qwen 模型名换成 MiniMax，也不要用 `pipeline.py voice` 重合成已经导入的 MiniMax 音频。

已实测的一组设置：`speech-2.8-hd`、`need_noise_reduction=true`、`need_volume_normalization=false`、`language_boost=Chinese`；文本不含 Qwen 的 `[excited]`／`[sad]`／`[curious]` 标签。用户认可的是开启参考样本降噪后生成的约 25 秒试听；完整稿约 99 秒的文字核对、分段和视频生成也已跑通。音质优劣是本次试听结论，不构成模型间的普遍排名。

1. **检查样本**：MiniMax 上传规范是 MP3／M4A／WAV、10 秒至 5 分钟、最多 20 MB。每次使用前核对官方现行要求。已有 15.9 秒样本成功，无需仅因换引擎让用户重录。
2. **上传**：`POST https://api.minimax.cn/v1/files/upload`，Bearer 鉴权，multipart 字段 `purpose=voice_clone` 和 `file`。让 HTTP 库生成 multipart boundary；保存成功返回的 `file.file_id`，重跑优先复用，避免重复上传。
3. **复刻与短段试听**：`POST /v1/voice_clone`。本次实测请求形状：

   ```json
   {
     "file_id": 123456789,
     "voice_id": "AvatarCleanUnique001",
     "model": "speech-2.8-hd",
     "text": "从用户原稿截取的两三段完整句子",
     "language_boost": "Chinese",
     "need_noise_reduction": true,
     "need_volume_normalization": false,
     "aigc_watermark": false
   }
   ```

   file_id 用上传结果；voice_id 每个新版本唯一，字母开头、长度 8–256、只含字母数字下划线连字符且末尾不是分隔符。改变样本或降噪设置时新建 voice_id；上传文件可以复用，旧音色和试听保留。下载 `demo_audio` 到本地提供试听，链接有时效，不能只保存远程 URL。

4. **听感确认**：约 20–30 秒的目标长度以实际生成结果为准。询问句尾电子音、停顿底噪、相似度及降噪后发闷／失真。参考样本降噪发生在复刻阶段，不等于对成品做后期滤波；换参数后应新建音色重试。用户认可后才扩展全文，避免为同一问题重复生成整篇。
5. **全文合成**：`POST /v1/t2a_v2`，使用同一个认可的 voice_id；成功请求示例：

   ```json
   {
     "model": "speech-2.8-hd",
     "text": "用户确认的全文原文",
     "stream": false,
     "voice_setting": {"voice_id": "AvatarCleanUnique001", "speed": 1, "vol": 1, "pitch": 0},
     "audio_setting": {"sample_rate": 32000, "format": "wav", "channel": 1},
     "language_boost": "Chinese",
     "output_format": "hex",
     "aigc_watermark": false
   }
   ```

   将 `data.audio` 的十六进制解码为 WAV，不把编码内容打印到工具输出。检查 HTTP 状态和 `base_resp.status_code == 0`，HTTP 200 仍可能业务失败。保存模型、voice_id、样本 SHA、降噪设置、原稿 SHA、试听确认原话、`trace_id`、`extra_info` 和实际输出路径；不保存 Key。

每次付费请求先说明动作；用户已要求换引擎并配置 Key 可执行已说明的试听方案，不能据此扩展成批音色试验。超时且结果不明时先核对已保存状态，不盲目创建新音色或重新合成。账户余额、鉴权、实名认证或复刻权限错误直接报告；不要升级付费档位。

## 外部音频交接契约

这是独立 API 或用户录音的导入方式，不是假装它由 Qwen `synth.py` 生成。当前没有内置 import 命令，调用方须用程序完成以下交接并验证；不要手填估计时长或伪造指纹。

1. 通过 `project.py init --copy <原稿>` 建项目。文案哈希只识别文字，**不识别供应商和音色**；保留旧版本，新路线用独立 `DH_WORKSPACE` 或独立对比目录，记录 provider，避免命中旧配音。
2. 验证源音频是单声道 16-bit PCM WAV；本次 MiniMax 32 kHz 文件可直接使用，不必升采样到 48 kHz。其他格式先在导入前转换，不调速。导入后原声保持不变。
3. 将完整原声写入 `out/merged.wav` 和 `out/seg_01.wav`。**这是一整段全文，不是按句或按 14 秒切分的音频。**
4. 根据真实 WAV 帧数生成 `out/timeline.json`，时长 `nframes / framerate`，未裁剪的完整源文件 `trim_start=0`。`audio_sha` 使用 SHA256 前 16 位，与 `_util.file_sha()` 一致。契约：

   ```text
   timeline = {
     provider, model, voice_id,
     total_seconds: WAV 实测时长,
     audio_sha: merged.wav 的 SHA256 前16位,
     segments: [{i: 1, chars: 原稿去空白字数, text: 原稿,
                 start: 0.0, end: WAV 实测时长, trim_start: 0.0,
                 audio_sha: seg_01.wav 的 SHA256 前16位}]
   }
   ```

   同步保存独立的提供商元数据，以及项目 `voice.json` 的 provider／model／voice_id。只有 merged.wav 而没有 seg_01.wav 和 timeline.json，`align_words.py` 会失败。导入程序生成这些记录；对齐以后不再手改它们。
5. 对新音频依次运行 `align_words.py --yes` → `verify_audio.py` → `pipeline.py segments`，随后处理图片、提示词和费用预览。MiniMax 的原生字幕时间也可留作对照，但尚未验证能直接替换本技能的 words.json。
6. 视频确认绑定**完整 WAV 的指纹**；短段音色认可不是对所有新生成全文的试听确认，也不是视频费用授权。完整配音和具体视频费用仍需按 SKILL.md 确认。

Qwen 对比版本用 `synth.py --variant <name>`，对齐、核对使用 `--out out_<name>`；数字人分段只读正式 `out/`。明确替换样本时 `clone_voice.py` 要加 `--force`，否则即使传了新 `--sample` 也可能复用旧 voice.json。音色 ID 与提供商、目标模型绑定，不能跨引擎复用。

## 计费与验证边界

- `usage_characters` 不一定等于可见文案字数；保留接口计量，不凭字符数自行断言最终费用。
- 本次 MiniMax 全文为约 99.02 秒；百炼文字相似度 1.000，分段为 10 段且切点均在句末停顿。这说明该链路可工作，不能保证以后每份音频都无错位或无噪音。
- 视频生成预览 RH 币和接口回报人民币不能直接比较或自行换算。分别报告参考估算、实际接口返回及缺失字段，最终以后台账单为准；TTS 与视频费用分开。

## 官方接口参考

- [上传复刻音频](https://platform.minimax.cn/docs/api-reference/voice-cloning-uploadcloneaudio)
- [快速复刻](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone)
- [同步 TTS](https://platform.minimax.cn/docs/api-reference/speech-t2a-http)

接口和模型版本会变化，执行前核对官方文档；本文参数为 2026-11-01 的本地实测记录。

## 当前默认选择

2026-11-02 用户在确认口语化全文和视频后，明确指定 **MiniMax 2.8 HD 为默认**，取代此前 Qwen 3.1 TTS Plus 默认选择。适用于后续未指定模型的请求；明确选择其他模型时遵从。MiniMax 2.6 fluent 与 Qwen Plus 均保留为可选，现有项目不因默认变更重做。统一口语底稿、模型适配和已确认参数见 [文本预处理](text-preparation.md)。

Plus 与 Flash 各自使用绑定目标模型的音色，不能互换 voice_id。Qwen 专用工具 clone_voice.py 与 synth.py 会核对绑定模型；不匹配时先报告并按目标模型创建／选择音色，不能把 Flash 缓存当成 Plus 试听。四模型比较的无标签自动语气只验证了约十秒片段，不能外推整篇或所有情绪设置。
