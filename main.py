import sys
import asyncio
import qasync
from PyQt5.QtWidgets import QApplication
from Backend.mainwindow import ModernTelegramGUI

def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = ModernTelegramGUI()
    window.show()
    with loop:
        loop.run_forever()

if __name__ == '__main__':
    main()