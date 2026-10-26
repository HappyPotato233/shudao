import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import permission from './directives/permission'
import { enableDialogDrag } from './utils/dialogDrag'
import './styles/theme.css'
import './styles/brandcard.css'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.directive('permission', permission)

// 启用全局弹窗拖拽：所有 el-dialog / ElMessageBox 均可拖动头部移动
enableDialogDrag()

app.mount('#app')
