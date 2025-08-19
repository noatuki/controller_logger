import pygame
import time


class InputReader:
    def __init__(self):
        pygame.init()
        # ダミーウィンドウ生成（DirectInput対策・枠なし最小化）
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("ゲームパッドが接続されていません")
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

    def close(self):
        """ジョイスティックとpygame.joystickのリソース解放"""
        try:
            self.joystick.quit()
        except Exception:
            pass
        pygame.joystick.quit()
        pygame.quit()

    def read(self):
        """1フレーム分の入力を取得"""
        pygame.event.pump()
        timestamp = time.time()
        axes = [self.joystick.get_axis(i) for i in range(self.joystick.get_numaxes())]
        buttons = [self.joystick.get_button(i) for i in range(self.joystick.get_numbuttons())]
        return timestamp, axes, buttons

    def get_headers(self):
        """CSVヘッダを返す"""
        headers = ["timestamp"]
        headers += [f"axis{i}" for i in range(self.joystick.get_numaxes())]
        headers += [f"button{i}" for i in range(self.joystick.get_numbuttons())]
        return headers
