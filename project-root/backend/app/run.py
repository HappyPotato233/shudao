"""开发服务器启动脚本

用法（在任意目录执行均可）:
    python run.py [host] [port]

默认启动地址: http://127.0.0.1:8000
"""
import sys
from pathlib import Path

import uvicorn

# 把 backend 目录加入 sys.path，确保 `app` 包可被导入
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    uvicorn.run("app.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
