# AGENTS.md — InkSpectrum

> **面向对象**：维护 / 开发 InkSpectrum 的 AI Agent（Kilo, Claude Code, Cursor, etc.）
> **当前阶段**：🟡 **MVP 完成 — 管道已跑通，待完善**
> **配套文档**：
> - 路线图：`.kilo/plans/2026-09-07-inkspectrum-roadmap.md`
> - 技能目录：`.kilo/skills/`（inkspectrum-orchestrator, extraction, script-generation, tts, image-asset, video-asset, manim-renderer, remotion-renderer）
> - 管道定义：`packages/textbook-pipeline/src/textbook_pipeline/`
> - 核心模型：`packages/textbook-pipeline/src/textbook_pipeline/models/`

---

## 〇、快速验证（AI Agent 必读）

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# 1. 验证 Phase 1 — PDF 提取
python packages/textbook-pipeline/scripts/enrich_chapter.py

# 2. 验证 Phase 2 — 脚本生成（AI 助手驱动，无需 LLM API）
# 见下方「三、AI 驱动脚本生成」

# 3. 验证 Phase 3 — TTS 音频
python packages/textbook-pipeline/scripts/run_phase3_tts.py

# 4. 验证 Phase 4 — 视频渲染
python packages/textbook-pipeline/scripts/run_phase4_render.py

# 输出: packages/textbook-pipeline/projects/english_pipeline_output/chapter_video.mp4
```

---

## 一、项目定位

InkSpectrum 是一个 **教科书 → 教育视频** 的自动化管道，将 PDF 教科书转换为配有旁白、动画和测验的教学视频。

**核心流程**：
```
PDF 教科书 → Phase 1 提取 → Phase 2 脚本 → Phase 3 TTS → Phase 4 渲染 → MP4 视频
```

**关键特性**：
- **AI 助手即 LLM**：脚本生成由 AI 助手（Kilo/Claude Code）直接编写 JSON，不依赖外部 LLM API
- **免费 TTS**：Edge TTS（无需 API Key）
- **本地渲染**：FFmpeg + Pillow（无需云服务）
- **完全离线可用**：Phase 2（脚本）由 AI 助手生成，Phase 3/4 完全本地

---

## 二、技术栈

| 层 | 选型 |
|------|------|
| 语言 | Python 3.10+ |
| 数据模型 | Pydantic v2 |
| PDF 提取 | PyMuPDF, OpenDataLoader, Docling |
| TTS | edge-tts（免费，无需 API Key） |
| 视频渲染 | FFmpeg + Pillow（静态幻灯片 + 音频合成） |
| 未来渲染 | Remotion (Node.js), Manim (数学动画), ModelsLab (AI 图像/视频) |
| 配置 | YAML (`config.yaml`) + `.env`（仅 ModelsLab/Stock Media 等可选服务） |
| 日志 | `logging.getLogger(__name__)` |
| 检查点 | JSON 文件（`phase2_checkpoint.json`） |
| Agent 驱动 | AI 助手直接读取/写入 JSON 状态文件 |

---

## 三、AI 驱动脚本生成（OpenMontage Pattern P2）

### 核心理念

> **No LLM API key in runtime — the agent IS the LLM.**

在 OpenMontage 模式中，AI 助手（Kilo, Claude Code 等）直接编写脚本 JSON，而不是通过 API 调用 LLM。这意味着：

1. **无需 Groq/AnyAPI API Key** 即可生成脚本
2. **无速率限制** — AI 助手不受 Token Per Minute 限制
3. **无解析错误** — AI 助手直接写入有效 JSON
4. **上下文感知** — AI 助手理解整个章节结构，不只是单个 Section

### 执行流程

当 AI 助手需要生成脚本时：

1. **读取** `chapter.json` — 获取所有 Section 的 title, content_text, type
2. **分析** — 识别理论部分 vs 练习部分
3. **生成** `phase2_script_scenes.json` — 为每个 Section 创建 ScriptScene

### ScriptScene 结构

```json
{
  "id": "scene_sec_001_0",
  "title": "At the Beach 1",
  "section_ref": "sec_001",
  "voiceover_lines": [
    {
      "text": "Hello friends! Today we will learn about...",
      "duration_seconds": 5.0,
      "pause_after": 0.5,
      "audio_path": "audio/scene_sec_001_0_line_1.mp3"
    }
  ],
  "scene_steps": [
    {
      "type": "title",
      "text": "At the Beach",
      "at": 0.0,
      "duration": 3.0
    },
    {
      "type": "text",
      "text": "Varun and Vidya are at the beach...",
      "at": 3.0,
      "duration": 5.0
    }
  ],
  "duration_seconds": 10.0,
  "notes": ""
}
```

### SceneStep 词汇表（受约束）

**通用**：`title`, `subtitle`, `text`, `clear`

**英语/人文**：`word_highlight`, `sentence_token`, `vocabulary_card`, `pronunciation_guide`, `poem_card`, `dialogue_bubble`, `storyboard_frame`

**数学**：`latex_inline`, `latex_block`, `polygon`, `circle`, `rectangle`, `triangle`, `angle_arc`, `axes_2d`, `axes_3d`, `plot_curve`, `number_line`, `fraction_bar`, `grid`

**社会研究**：`timeline`, `map_marker`, `cause_effect_chain`, `comparison_table`, `geographic_map`, `historical_figure`, `primary_source`

**练习**：`question_card`, `worked_step`, `answer_reveal`

### 理论部分 vs 练习部分

| 部分类型 | SceneStep 模式 | 旁白风格 |
|---------|---------------|---------|
| `theoretical` | title → text → word_highlight → text → clear | 讲解式，讲故事 |
| `exercise` | question_card → worked_step → answer_reveal | 引导式，逐步解答 |

---

## 四、目录结构

```
D:\new_video_pip\
├── AGENTS.md                       # 本文件 — Agent 操作指南
├── config.yaml                     # 全局配置（LLM, budget, paths）
├── .env                            # 密钥（仅 ModelsLab/Stock Media）
├── Makefile                        # 构建目标
├── packages/
│   └── textbook-pipeline/
│       ├── src/textbook_pipeline/
│       │   ├── models/             # Pydantic 模型
│       │   │   ├── chapter.py      # ChapterNode, SectionNode
│       │   │   ├── script.py       # ScriptScene, SceneStep, VoiceoverLine
│       │   │   └── assets.py       # ImageAsset, VideoAsset, AudioAsset
│       │   ├── core/
│       │   │   ├── ingestion/      # PDF 提取器
│       │   │   ├── script/         # 脚本生成（LLM 回退）
│       │   │   ├── generation/     # TTS, Image, Video 客户端
│       │   │   └── composition/    # 视频渲染
│       │   └── cli.py              # 命令行入口
│       ├── scripts/
│       │   ├── enrich_chapter.py   # Phase 1: 丰富 chapter.json
│       │   ├── run_phase2_tools.py # Phase 2: 脚本生成
│       │   ├── run_phase3_tts.py   # Phase 3: TTS 音频
│       │   └── run_phase4_render.py # Phase 4: 视频渲染
│       └── projects/
│           └── english_pipeline_output/
│               ├── chapter.json              # Phase 1 输出
│               ├── phase2_script_scenes.json # Phase 2 输出（AI 助手生成）
│               ├── audio/                    # Phase 3 输出
│               └── chapter_video.mp4         # Phase 4 输出
├── lib/                            # 核心运行时
│   ├── config_model.py             # Pydantic 配置模型
│   ├── checkpoint.py               # 检查点系统
│   ├── pipeline_loader.py          # YAML 管道加载器
│   ├── tool_registry.py            # 工具注册表
│   └── env_loader.py               # 环境变量加载
├── tools/                          # 管道工具
│   ├── base_tool.py                # 工具基类
│   ├── script/                     # 脚本生成工具
│   └── ...                         # 其他工具
├── .kilo/
│   ├── skills/                     # Agent 技能
│   │   ├── inkspectrum-orchestrator/
│   │   ├── inkspectrum-extraction/
│   │   ├── inkspectrum-script-generation/
│   │   ├── inkspectrum-tts/
│   │   ├── inkspectrum-image-asset/
│   │   ├── inkspectrum-video-asset/
│   │   ├── inkspectrum-manim-renderer/
│   │   └── inkspectrum-remotion-renderer/
│   └── agents/                     # Agent 定义
└── vendor/                         # 第三方库
```

---

## 五、AI Agent 触发词

| 用户说法 | Agent 应执行的操作 | 说明 |
|---------|-------------------|------|
| **"生成完整视频"** | 执行完整管道：Phase 1 → 2 → 3 → 4 | 从 PDF 到 MP4 |
| **"修复 Phase 2"** | 检查 `phase2_script_scenes.json`，修复解析/内容问题 | 可能需要 AI 重新生成脚本 |
| **"修复 Phase 3"** | 检查 TTS 输出，重新生成失败的音频 | 运行 `run_phase3_tts.py` |
| **"修复 Phase 4"** | 检查渲染输出，重新渲染 | 运行 `run_phase4_render.py` |
| **"生成脚本"** | 读取 chapter.json，生成 phase2_script_scenes.json | AI 直接编写，无需 LLM API |
| **"跑一下"** | 从 Phase 2 或 Phase 3 继续管道 | 检查点自动恢复 |
| **"验证项目"** | 按「〇、快速验证」执行 | 检查所有阶段 |
| **"修复 Bug: ..."** | 定位 → 修复 → 自验 → 汇报 | 直接修复，不委派子 agent |

---

## 六、管道执行规范

### Phase 1: PDF 提取（enrich_chapter.py）

**输入**：PDF 教科书文件
**输出**：`chapter.json`（ChapterNode 结构）

**执行**：
```powershell
python packages/textbook-pipeline/scripts/enrich_chapter.py
```

**验证**：
- 所有 Section 都有非空 `content_text`
- `type` 字段正确（`theoretical` vs `exercise`）

### Phase 2: 脚本生成（AI 助手驱动）

**输入**：`chapter.json`
**输出**：`phase2_script_scenes.json`

**执行**（两种方式）：

**方式 A — AI 助手直接生成**（推荐，无 LLM API）：
1. AI 读取 `chapter.json`
2. AI 分析每个 Section 的内容
3. AI 直接写入 `phase2_script_scenes.json`

**方式 B — LLM API 回退**（当 AI 不可用时）：
```powershell
python packages/textbook-pipeline/scripts/run_phase2_tools.py
```

**验证**：
- 每个 Section 有且仅有 1 个 ScriptScene
- 每个 Scene 有 ≥ 2 个 voiceover_lines
- 每个 Scene 有 ≥ 2 个 scene_steps
- 理论部分使用 `title/text/word_highlight` 等教学词汇
- 练习部分使用 `question_card/worked_step/answer_reveal`

### Phase 3: TTS 音频（run_phase3_tts.py）

**输入**：`phase2_script_scenes.json`
**输出**：`audio/*.mp3` + `audio_manifest.json`

**执行**：
```powershell
python packages/textbook-pipeline/scripts/run_phase3_tts.py
```

**验证**：
- 每个 voiceover_line 有对应的 `.mp3` 文件
- `audio_manifest.json` 记录所有音频文件

### Phase 4: 视频渲染（run_phase4_render.py）

**输入**：`phase2_script_scenes_with_audio.json` + `audio/`
**输出**：`chapter_video.mp4`

**执行**：
```powershell
python packages/textbook-pipeline/scripts/run_phase4_render.py
```

**验证**：
- `chapter_video.mp4` 存在且 > 1MB
- 视频时长 ≈ 音频总时长
- 所有音频片段都包含在视频中

---

## 七、完整管道执行流程（AI 助手版）

```
用户说 "生成完整视频" 或 "从 PDF 生成视频"

1. AI 助手检查 Phase 1 输出
   - 如果 chapter.json 不存在或内容为空 → 运行 enrich_chapter.py

2. AI 助手生成 Phase 2 脚本
   - 读取 chapter.json
   - 为每个 Section 生成 ScriptScene
   - 写入 phase2_script_scenes.json

3. AI 助手运行 Phase 3 TTS
   - 执行 run_phase3_tts.py
   - 等待 63 个音频文件生成

4. AI 助手运行 Phase 4 渲染
   - 执行 run_phase4_render.py
   - 等待 chapter_video.mp4 生成

5. AI 助手验证输出
   - 检查文件大小 > 1MB
   - 汇报生成结果
```

---

## 八、BugFix 工作流

用户说 **"修复 Bug: ..."** 时按以下流程执行：

```
1. 定位
   - 阅读用户描述的 bug 现象
   - 检查对应 Phase 的输出文件
   - 复现 bug（重新运行该 Phase）

2. 修复
   - 直接执行修复
   - 确保修复不违反「共享知识规范」

3. 自验
   - 重新运行该 Phase
   - 验证输出正确

4. 汇报
   - 向用户说明：根因、修复方案、涉及文件
   - 附验证结果
```

---

## 九、共享知识规范

### 9.1 日志前缀

| 前缀 | 模块 |
|------|------|
| `[Phase1]` | PDF 提取 |
| `[Phase2]` | 脚本生成 |
| `[Phase3]` | TTS 音频 |
| `[Phase4]` | 视频渲染 |
| `[TTS]` | edge-tts 调用 |
| `[Renderer]` | FFmpeg 渲染 |
| `[Checkpoint]` | 检查点读写 |

### 9.2 错误处理

| 场景 | 策略 |
|------|------|
| TTS 失败 | 记录错误，使用静音占位 |
| 渲染失败 | 记录错误，跳过该场景 |
| LLM API 失败 | 回退到 AI 助手生成 |
| 检查点 | 每个 Section 完成后写入，失败后可恢复 |

### 9.3 视频-音频同步

```python
# 每个场景的时长 = 该场景所有音频片段时长之和 +  pauses
scene_duration = sum(audio_durations) + sum(pause_afters)
```

### 9.4 向后兼容

- `chapter.json` 格式保持稳定
- `phase2_script_scenes.json` 格式保持稳定
- 新增字段必须有默认值

---

## 十、铁律

1. **AI 助手优先**：优先使用 AI 助手生成脚本，而非调用 LLM API
2. **无 API Key 也能跑通**：Phase 3/4 完全免费，Phase 2 由 AI 助手驱动
3. **检查点即保存**：每个 Phase 的输出都是持久化文件，可随时恢复
4. **验证即汇报**：每个 Phase 完成后汇报统计信息（文件数、大小、时长等）
5. **错误即处理**：遇到错误时记录日志并继续，不要崩溃退出

---

## 十一、当前状态（2026-09-09）

| 组件 | 状态 | 备注 |
|------|------|------|
| Phase 1: PDF 提取 | ⚠️ 50% 空内容 | enrich_chapter.py 可从 opendataloader 补充 |
| Phase 2: 脚本生成 | ✅ AI 助手可生成 | 18/20 真实场景，2 个 fallback |
| Phase 3: TTS | ✅ 64 个音频文件 | Edge TTS，免费 |
| Phase 4: 渲染 | ✅ 6.3MB MP4 | FFmpeg + Pillow |
| 最终视频 | ✅ 存在 | chapter_video.mp4 |
| Section 分类 | ⚠️ 需修正 | 10 个 Section 标记为 theoretical，应为 exercise |
| LLM API | ❌ 已弃用 | 改用 AI 助手驱动 |

---

*文档版本：v1.0 | 更新日期：2026-09-09 | 阶段：🟡 MVP 完成 — 管道已跑通，待完善*
