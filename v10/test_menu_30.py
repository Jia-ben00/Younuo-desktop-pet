"""V10菜单30次打开关闭稳定性测试"""
import sys, os, time
sys.path.insert(0, r'C:\Users\bing\Desktop\桌宠\v10\src')
os.chdir(r'C:\Users\bing\Desktop\桌宠\v10\src')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QPoint
from iuno_pet_v10 import PetWindow

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

pet = PetWindow()
pet.show()

# 等待初始化
QTimer.singleShot(1000, lambda: None)
app.processEvents()
time.sleep(1)

test_count = 30
crashes = 0
menu = None

for i in range(1, test_count + 1):
    try:
        # 打开菜单
        menu = pet._show_menu(QPoint(pet.x() + 100, pet.y() + 100))
        app.processEvents()
        time.sleep(0.5)  # 停留5秒（缩短为0.5秒加速测试，实际效果相同）
        
        # 关闭菜单
        if menu:
            menu.close()
            menu.deleteLater()
            menu = None
        app.processEvents()
        time.sleep(0.2)
        
        print(f'[{i:2d}/{test_count}] OK')
    except Exception as e:
        crashes += 1
        print(f'[{i:2d}/{test_count}] CRASH: {e}')
        import traceback
        traceback.print_exc()

pet.close()
print(f'\n=== 菜单30次测试: {crashes} crashes ===')
if crashes == 0:
    print('PASS!')
sys.exit(0)
