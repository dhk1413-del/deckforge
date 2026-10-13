import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ToastProvider } from './components/Toast'
import './index.css'

const el = document.getElementById('root')
if (!el) throw new Error('#root 节点不存在，检查 index.html')

createRoot(el).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
