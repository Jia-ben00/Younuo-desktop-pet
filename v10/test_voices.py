"""V10语音全量测试脚本 - 依次播放所有39个语音文件"""
import os, sys, time, winsound

VOICE_DIR = r'C:\Users\bing\Desktop\桌宠\v10\assets\voice_v10'

# 所有语音文件列表
states = ['qiaotui', 'haixiu', 'sajiao', 'kaixin', 'shangxin', 'daimeng', 'toukan']
tiers = [1, 2, 3, 4, 5]
specials = ['levelup', 'gaobai_1', 'gaobai_2', 'gaobai_3']

all_voices = []
for s in states:
    for t in tiers:
        all_voices.append(f'{s}_{t}')
all_voices.extend(specials)

print(f'=== V10语音全量测试（共{len(all_voices)}个）===')
print(f'语音目录: {VOICE_DIR}')
print()

success = 0
failed = []
skipped = []

for i, name in enumerate(all_voices, 1):
    wav = os.path.join(VOICE_DIR, f'{name}.wav')
    if not os.path.exists(wav):
        print(f'[{i:2d}/{len(all_voices)}] {name:20s} - 跳过（文件不存在）')
        skipped.append(name)
        continue
    
    size = os.path.getsize(wav)
    try:
        # 播放（异步）
        winsound.PlaySound(None, winsound.SND_PURGE)
        winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        # 等待播放（最多3秒）
        time.sleep(1.5)
        winsound.PlaySound(None, winsound.SND_PURGE)
        print(f'[{i:2d}/{len(all_voices)}] {name:20s} - OK ({size//1024}KB)')
        success += 1
    except Exception as e:
        print(f'[{i:2d}/{len(all_voices)}] {name:20s} - 失败: {e}')
        failed.append(name)

print()
print('=== 测试结果 ===')
print(f'总数: {len(all_voices)}')
print(f'成功: {success}')
print(f'失败: {len(failed)}')
print(f'跳过: {len(skipped)}')
if failed:
    print(f'失败列表: {failed}')
if skipped:
    print(f'跳过列表: {skipped}')
if success == len(all_voices):
    print('全部通过！')
