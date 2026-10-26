---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 619a68374c198f2d1dccd9a31deded68_c13bf7279a4011f1a98a525400f8a581
    ReservedCode1: R9qVaDOZrgEDIzd1DSKsmAUW2KvKxk97+4+NkO7jqVWqiK8C1TcvttFbXmzt/Sn33deaDfvA9AIndcKPRRE9Uhqu15AM1oS+k6AXHSUAwlpF/GhyyyRc/RNWKXGp3mqzF9NDuBjlRhXBj2CJaMEeHVw+WC9EcKhOPvNFCx9qayQvqJm6f4tYA+3XO/Y=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 619a68374c198f2d1dccd9a31deded68_c13bf7279a4011f1a98a525400f8a581
    ReservedCode2: R9qVaDOZrgEDIzd1DSKsmAUW2KvKxk97+4+NkO7jqVWqiK8C1TcvttFbXmzt/Sn33deaDfvA9AIndcKPRRE9Uhqu15AM1oS+k6AXHSUAwlpF/GhyyyRc/RNWKXGp3mqzF9NDuBjlRhXBj2CJaMEeHVw+WC9EcKhOPvNFCx9qayQvqJm6f4tYA+3XO/Y=
---

# 前端风格指南 — macOS 窗口风格（深色终端）

> 版本：v1.0 ｜ 适用：蜀道安全助手前端（Vue 3 + TypeScript + Element Plus）
> 风格基调：深色代码窗口、交通灯标题栏、克制圆角、终端隐喻

---

## 一、风格概述

本风格源自 macOS 窗口设计语言，核心特征是**"窗口感"与"终端隐喻"**：

- 深色背景（`#011522` 类蓝黑）模拟代码编辑器 / 终端环境
- 标题栏左上角"红黄绿"三色交通灯按钮，一眼识别为可操作窗口
- 圆角克制（8px），整体冷静、专业、聚焦内容
- 适合承载代码展示、日志输出、AI 对话、控制台类界面

适用场景：代码展示卡片、终端模拟器、AI 助手对话窗、日志/监控面板。

---

## 二、设计原则

| 原则 | 说明 |
|---|---|
| 深色优先 | 背景使用深蓝黑系，内容用浅色文字，营造"屏幕/终端"氛围 |
| 窗口隐喻 | 所有容器保留标题栏 + 内容区结构，交通灯作为窗口标识 |
| 克制圆角 | 统一 8px，不追求大圆角也不完全直角 |
| 交通灯语义 | 红=关闭、黄=最小化、绿=最大化，颜色不可随意更换 |
| 内容留白 | 标题栏与内容区分离，内容区保持呼吸感 |

---

## 三、色彩规范

| Token | 色值 | 用途 |
|---|---|---|
| `--color-window` | `#011522` | 窗口/卡片背景（深蓝黑） |
| `--color-panel` | `#0B1B2B` | 次级面板、内容区背景 |
| `--color-text` | `#E6EDF3` | 主文字（浅色） |
| `--color-text-dim` | `#8B949E` | 次要文字、占位符 |
| `--color-close` | `#FF605C` | 交通灯·关闭（红） |
| `--color-min` | `#FFBD44` | 交通灯·最小化（黄） |
| `--color-max` | `#00CA4E` | 交通灯·最大化（绿） |
| `--color-accent` | `#58A6FF` | 强调色、链接、高亮 |

> 规则：交通灯三色为语义色，仅用于窗口控制按钮，不用于业务状态。

---

## 四、字体与排版

| 项 | 规范 |
|---|---|
| 字体族 | 代码场景：`"JetBrains Mono", "Cascadia Code", Consolas, monospace`；正文：系统字体栈 |
| 标题 | `font-weight: 600`，字号 16–20px，浅色 |
| 正文 | `font-weight: 400`，字号 13–14px，`line-height: 1.6` |
| 代码 | 等宽字体，字号 12–13px，行高 1.5 |

---

## 五、间距与尺寸

| Token | 值 | 用途 |
|---|---|---|
| 窗口尺寸 | 190×254px（示例）/ 自适应容器 | 卡片基准 |
| 标题栏 | `padding: 9px`，高度约 28px | 交通灯区域 |
| 圆点 | 10×10px，间距 4px（`padding: 0 4px`） | 交通灯 |
| 圆角 | 8px（统一） | 窗口/面板 |
| 内容区 | `padding: 16–24px` | 内容留白 |

---

## 六、组件规范

### 1. 窗口卡片（Window Card）

- 容器：深色背景 + 8px 圆角，可选 1px 浅色描边（`rgba(255,255,255,0.08)`）增强边界
- 结构：标题栏（`.tools`）+ 内容区（`.card__content`）两部分

### 2. 交通灯（Traffic Lights）

- 三个 10px 圆形，横向排列，间距 4px
- 颜色固定：红 `#FF605C` / 黄 `#FFBD44` / 绿 `#00CA4E`
- 可选增强：hover 时显示图标（× / − / ＋），点击触发对应窗口操作

### 3. 内容区（Content）

- 与标题栏分离，独立 padding
- 可承载：代码块、日志流、对话消息、表单

---

## 七、交互与动效规范

| 状态 | 动效 | 说明 |
|---|---|---|
| 交通灯 hover | 亮度提升 / 显示操作图标 | 提示可点击 |
| 交通灯 active | `scale(0.9)` | 按下反馈 |
| 窗口 hover | 可选 1px 描边高亮 | 提示可聚焦 |
| 内容滚动 | 细滚动条（深色主题） | 保持整体风格 |

> 动效统一 `transition: 0.2s ease`，深色主题下避免过亮过渡。

---

## 八、参考实现（可直接复用）

```vue
<style scoped>
  .card {
    width: 190px;
    height: 254px;
    margin: 0 auto;
    background-color: #011522;
    border-radius: 8px;
    z-index: 1;
  }
  .tools {
    display: flex;
    align-items: center;
    padding: 9px;
  }
  .circle {
    padding: 0 4px;
  }
  .box {
    display: inline-block;
    align-items: center;
    width: 10px;
    height: 10px;
    padding: 1px;
    border-radius: 50%;
  }
  .red {
    background-color: #ff605c;
  }
  .yellow {
    background-color: #ffbd44;
  }
  .green {
    background-color: #00ca4e;
  }
</style>
<template>
  <div class="card">
    <div class="tools">
      <div class="circle"><span class="red box"></span></div>
      <div class="circle"><span class="yellow box"></span></div>
      <div class="circle"><span class="green box"></span></div>
    </div>
    <div class="card__content"></div>
  </div>
</template>
```

---

## 九、使用注意事项

1. **交通灯语义不可变**：红黄绿对应关闭/最小化/最大化，勿用于业务状态标识。
2. **深色主题可访问性**：文字与背景对比度需 ≥ 4.5:1；`#8B949E` 仅用于次要信息。
3. **内容区必须填充**：窗口外壳需搭配实际内容（代码/日志/对话），避免空壳。
4. **响应式**：固定尺寸（190×254px）在移动端需改为自适应宽度。
5. **与 Element Plus 共存**：深色主题需覆盖 Element Plus 默认浅色变量（`--el-bg-color` 等），建议封装为独立主题。
*（内容由AI生成，仅供参考）*
