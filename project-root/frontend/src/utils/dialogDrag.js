/**
 * 全局弹窗拖拽：让所有 Element Plus 弹窗（el-dialog / el-message-box）可被鼠标拖动。
 * 采用事件委托 + 头部 mousedown 拖动的零侵入方案，动态出现的弹窗也能生效。
 */
export function enableDialogDrag() {
  // 命中弹窗头部：普通对话框 + ElMessageBox 确认框
  const HEADER_SELECTOR = '.el-dialog__header, .el-message-box__header'
  const DIALOG_SELECTOR = '.el-dialog, .el-message-box'

  const onMouseDown = (e) => {
    const header = e.target.closest(HEADER_SELECTOR)
    if (!header) return
    const dialog = header.closest(DIALOG_SELECTOR)
    if (!dialog) return
    // 忽略头部上的可交互元素（关闭按钮、按钮、输入框等），避免与点击/文本选择冲突
    if (e.target.closest('button, input, textarea, a, .el-dialog__headerbtn, .el-message-box__headerbtn')) return
    // 忽略非鼠标左键
    if (e.button !== 0) return

    e.preventDefault()

    const rect = dialog.getBoundingClientRect()
    const startX = e.clientX
    const startY = e.clientY
    const offsetLeft = rect.left
    const offsetTop = rect.top

    const onMove = (ev) => {
      dialog.style.position = 'absolute'
      dialog.style.margin = '0'
      dialog.style.left = `${offsetLeft + ev.clientX - startX}px`
      dialog.style.top = `${offsetTop + ev.clientY - startY}px`
    }

    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  document.addEventListener('mousedown', onMouseDown)
}
