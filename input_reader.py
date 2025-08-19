import os
import pygame
import time


class InputReader:
    def __init__(self):
        # ワーカースレッド側で実ウィンドウを作らない（Qtと競合しフリーズの原因）
        try:
            if os.name == "nt":
                os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        except Exception:
            pass
        pygame.init()
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
        # D-Pad（十字キー）をbuttons配列に追加
        if self.joystick.get_numhats() > 0:
            hat = self.joystick.get_hat(0)  # (x, y)
            # ↑↓←→をボタンとして追加
            buttons += [int(hat[1] == 1), int(hat[1] == -1), int(hat[0] == -1), int(hat[0] == 1)]
        return timestamp, axes, buttons

    def get_headers(self):
        """CSVヘッダを返す"""
        headers = ["timestamp"]
        headers += [f"axis{i}" for i in range(self.joystick.get_numaxes())]
        headers += [f"button{i}" for i in range(self.joystick.get_numbuttons())]
        if self.joystick.get_numhats() > 0:
            headers += ["dpad_up", "dpad_down", "dpad_left", "dpad_right"]
        return headers
