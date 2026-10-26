import type { Directive } from 'vue'
import { useUserStore } from '@/stores/user'

const permission: Directive = {
  mounted(el, binding) {
    const required = binding.value as string | string[]
    if (!required || required.length === 0) return
    const store = useUserStore()
    const roles = Array.isArray(required) ? required : [required]
    if (!roles.includes(store.role as string)) {
      el.parentNode?.removeChild(el)
    }
  },
}

export default permission
