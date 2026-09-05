"""V10语音播放完整测试"""
import sys, os, time
sys.path.insert(0, r'C:\Users\bing\Desktop\桌宠\v10\src')
os.chdir(r'C:\Users\bing\Desktop\桌宠\v10\src')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

# 模拟EXE环境，设置voice_v10路径到dist
import iuno_pet_v10
# 强制设置voice_v10路径
original_init = iuno_pet_v10.VoiceManagerV10.__init__
def patched_init(self):
    from PyQt5.QtCore import QObject
    QObject.__init__(self)
    self.enabled = True
    self._voice_dir = r'C:\Users\bing\Desktop\桌宠\dist\voice_v10'
    print('VoiceManagerV10 init, dir:', self._voice_dir)
    print('Files:', len([f for f in os.listdir(self._voice_dir) if f.endswith('.wav')]))
iuno_pet_v10.VoiceManagerV10.__init__ = patched_init

pet = iuno_pet_v10.PetWindow()
pet.show()
app.processEvents()
time.sleep(1)

print('\n=== 测试v10_interact ===')
for action in ['poke', 'play', 'feed', 'drag']:
    print(f'\nTesting {action}...')
    try:
        pet.v10_interact(action)
        app.processEvents()
        time.sleep(1.5)
        print(f'  {action}: OK')
    except Exception as e:
        print(f'  {action}: ERROR - {e}')
        import traceback
        traceback.print_exc()

pet.close()
print('\n=== 测试完成 ===')
sys.exit(0)
