from Arknights.addons.common import CommonAddon
from automator import AddonBase
from automator.addon import cli_command

from enum import Enum
import cv2
from imgreco import ocr
from imgreco.common import get_nav_button_back_rect, recognize_dialog, get_dialog_right_button_rect
from imgreco.recruit import common
from util.cvimage import Image
from util import cvimage


class InterestBearing(AddonBase):

    class Scence(Enum):
        main = -1  #主页
        eventCover = 0  # 活动界面
        operatorFillEnerge = 1  # 干员补充能量
        gameMap = 2
        battleEntry = 3
        battleStage = 4
        onExitBattle = 5
        onExitGame = 6

    class Period(Enum):
        gettingInfo = -1  # 获取现有分数
        checkGameStart = 0  # 是否有未结束的游戏
        loopStart = 1  # 循环开始
        selectOperator = 2  # 干员选择
        fillEnerge = 3  # 回复体力
        startGame = 4
        loopEnd = 5

    step: Period
    scence: Scence
    point: int = 0
    day = 1

    def getOwnPoint(self):

        self.wait_and_tap_roi(self.load_roi("InterestBearing/pointButton"))
        self.logger.info("进入分数面板")
        self.wait_for_roi(self.load_roi("InterestBearing/pointSymbol"))
        img: Image = self.screenshot()
        vw, vh = common.get_vwvh(img)
        img = img.crop(((9.063 * vw, 81.111 * vh, 14.625 * vw, 84.111 * vh)))
        # 二值化
        img = cvimage.fromarray(
            cv2.threshold(
                img.convert("L").array, 127, 255, cv2.THRESH_BINARY_INV)[1])

        engine = ocr.acquire_engine_global_cached('zh-cn')
        self.point = int(
            engine.recognize(img,
                             int(vh * 20),
                             hints=[ocr.OcrHint.SINGLE_LINE],
                             char_whitelist="0123456789").text.replace(
                                 ' ', ''))
        self.logger.info("获取繁荣证章数量,当前繁荣证章:%d" % self.point)
        #返回
        self.tap_rect(get_nav_button_back_rect(self.viewport), post_delay=2)
        self.step = self.Period.loopStart

    def getRewardPoint(self):
        img: Image = self.screenshot()
        vw, vh = common.get_vwvh(img)
        img = img.crop((50.938 * vw, 52.778 * vh, 53.688 * vw, 57.111 * vh))
        # 二值化
        img = cvimage.fromarray(
            cv2.threshold(
                img.convert("L").array, 127, 255, cv2.THRESH_BINARY_INV)[1])

        engine = ocr.acquire_engine_global_cached('zh-cn')
        po = int(
            engine.recognize(img,
                             int(vh * 20),
                             hints=[ocr.OcrHint.SINGLE_LINE],
                             char_whitelist="0123456789").text.replace(
                                 ' ', ''))
        self.logger.info("本次行动获取了%d繁荣证章" % po)
        self.point += po
        #返回
        self.tap_rect((47.875 * vw, 85.667 * vh, 52.188 * vw, 93.000 * vh),
                      post_delay=2)

    # 结束游戏进入下一次循环
    def finishGame(self):
        self.logger.info("结束生息演算")
        self.wait_and_tap_roi(self.load_roi("InterestBearing/giveUp"))
        while True:
            dlgtype, ocr = recognize_dialog(self.screenshot())
            if "放弃" in ocr and "演算" in ocr:
                self.tap_rect(get_dialog_right_button_rect(self.screenshot()),
                              post_delay=5)
                break
        self.wait_and_tap_roi(self.load_roi("InterestBearing/checkRes"))
        self.wait_and_tap_roi(
            self.load_roi("InterestBearing/checkResComfirmButton"))
        if self.wait_for_roi(self.load_roi("InterestBearing/pointReward")):
            self.getRewardPoint()
        else:
            self.logger.error("未获得繁荣证章")
        self.day = 1

    @cli_command("bearing")
    def bearing(self, args):
        """
        bearing
        自动挂机生息演算
        """
        self.step = self.Period.gettingInfo
        self.scence = self.Scence.main
        self.logger.info("返回主页")
        self.addon(CommonAddon).back_to_main()
        self.step = self.Period.gettingInfo
        while self.point < 6000:
            screen = self.screenshot()
            if self.scence == self.Scence.main:
                if self.step == self.Period.gettingInfo:
                    self.wait_and_tap_roi(
                        self.load_roi("InterestBearing/entrance"), )
                    self.logger.info("进入活动")
                    self.scence = self.Scence.eventCover
                    continue

            if self.scence == self.Scence.eventCover:
                # 游戏状态判断
                if self.step == self.Period.checkGameStart:
                    if match := self.match_roi("InterestBearing/giveUp"):
                        self.step = self.Period.loopEnd
                        continue
                    elif match := self.match_roi(
                            "InterestBearing/startOperation"):
                        self.step = self.Period.loopStart
                        continue

                if self.step == self.Period.gettingInfo:
                    self.getOwnPoint()
                    self.step = self.Period.checkGameStart
                    continue
                if self.step == self.Period.loopStart:
                    self.logger.info("开始")
                    self.wait_and_tap_roi(
                        self.load_roi("InterestBearing/startOperation"), )
                    self.step = self.Period.selectOperator
                    self.scence = self.Scence.operatorFillEnerge

                    continue
                if self.step == self.Period.loopEnd:
                    self.finishGame()
                    self.step = self.Period.loopStart
                    continue
            if self.scence == self.Scence.operatorFillEnerge:
                if self.step == self.Period.selectOperator:
                    self.logger.info("进入干员选择")
                    self.wait_and_tap_roi(
                        self.load_roi("InterestBearing/operatorSelect"))
                    self.step = self.Period.fillEnerge
                    continue
                if self.step == self.Period.fillEnerge:
                    self.logger.info("回复干员体力")
                    self.wait_and_tap_roi(
                        self.load_roi("InterestBearing/fillEnergy"))
                    self.step = self.Period.startGame
                    continue
                if self.step == self.Period.startGame:
                    self.logger.info("演算开始")
                    self.wait_and_tap_roi(
                        self.load_roi("InterestBearing/startGame"))
                    self.scence = self.Scence.gameMap
                    continue
            if self.scence == self.Scence.gameMap:

                # 第五天退出
                if self.day >= 5:
                    self.scence = self.Scence.onExitGame
                    continue
                if match := self.match_roi("InterestBearing/skipReport",
                                           screenshot=screen):
                    self.tap_rect(match.bbox)
                    self.logger.info("跳过报告")
                    continue
                # 每日日报
                if match := self.match_roi("InterestBearing/dailyMessage",
                                           screenshot=screen):
                    self.tap_rect(match.bbox)
                    self.logger.info("关闭日报")
                    continue
                if match := self.match_roi("InterestBearing/maxMap",
                                           screenshot=screen):
                    vw, vh = common.get_vwvh(self.screenshot())
                    self.tap_rect(
                        (48.063 * vw, 46.444 * vh, 52.000 * vw, 53.333 * vh))
                    self.logger.info("放大地图")
                    continue
                if match := self.match_roi("InterestBearing/nextDay",
                                           screenshot=screen):
                    vw, vh = common.get_vwvh(self.screenshot())
                    self.tap_rect(match.bbox)
                    self.day += 1
                    self.logger.info("进入第%d天" % self.day)
                    continue

                try:
                    if match := self.match_roi("InterestBearing/startBattle",
                                               fixed_position=False,
                                               mode="L",
                                               method='sift',
                                               screenshot=screen):
                        self.scence = self.Scence.battleEntry
                        continue
                    if match := self.match_roi("InterestBearing/resourceArea",
                                               fixed_position=False,
                                               mode="L",
                                               method='sift',
                                               screenshot=screen):
                        self.logger.info("发现资源区")
                        self.tap_rect(match.bbox)
                        continue
                    if match := self.match_roi("InterestBearing/huntArea",
                                               fixed_position=False,
                                               mode="L",
                                               method='sift',
                                               screenshot=screen):
                        self.logger.info("发现捕猎区")
                        self.tap_rect(match.bbox)
                        continue
                except:
                    continue

            if self.scence == self.Scence.battleEntry:
                # if match := self.match_roi("InterestBearing/skipReport"):
                #     self.tap_rect(match.bbox)
                #     self.logger.info("跳过报告")
                #     self.scence = self.Scence.gameMap
                #     continue
                if match := self.match_roi("InterestBearing/dayDone",
                                           screenshot=screen):
                    self.logger.info("决断达到上限,无法进入战斗")
                    self.scence = self.Scence.gameMap
                    continue
                dlgtype, ocr = recognize_dialog(self.screenshot())
                if dlgtype == 'yesno':
                    if "确认开始行动" in ocr:
                        self.tap_rect(get_dialog_right_button_rect(
                            self.screenshot()),
                                      post_delay=5)
                        self.scence = self.Scence.battleStage
                        self.logger.info("确认开始行动")
                        continue
                try:
                    if match := self.match_roi("InterestBearing/startBattle",
                                               fixed_position=False,
                                               mode="L",
                                               method='sift',
                                               screenshot=screen):
                        self.logger.info("战斗！")
                        self.tap_rect(match.bbox)
                        continue
                except:
                    continue
                if match := self.match_roi("InterestBearing/prepareBattle",
                                           screenshot=screen):
                    self.logger.info("行动准备")
                    self.tap_rect(match.bbox)
                    continue
                if match := self.match_roi("InterestBearing/enterBattle",
                                           screenshot=screen):
                    self.logger.info("行动开始")
                    self.tap_rect(match.bbox)
                    continue
                if match := self.match_roi("InterestBearing/packButton",
                                           screenshot=screen):
                    self.logger.info("进入战斗界面")
                    self.scence = self.Scence.battleStage
                    self.delay(1)
                    continue
            if self.scence == self.Scence.battleStage:
                if match := self.match_roi("InterestBearing/exitBattleButton",
                                           screenshot=screen):
                    self.logger.info("尝试退出行动by exit")
                    self.tap_rect(match.bbox)
                    self.delay(2)
                    continue
                elif match := self.match_roi("InterestBearing/packButton",
                                             screenshot=screen):
                    self.logger.info("尝试退出行动by pack")
                    vw, vh = common.get_vwvh(self.screenshot())
                    self.tap_rect(
                        ((2.625 * vw, 3.222 * vh, 8.438 * vw, 12.444 * vh)))
                    self.delay(2)
                    continue
                if match := self.match_roi("InterestBearing/comfirmBattleExit",
                                           screenshot=screen):
                    self.logger.info("确认退出")
                    self.tap_rect(match.bbox)
                    self.scence = self.Scence.onExitBattle
                    self.delay(3)
                    continue
            if self.scence == self.Scence.onExitBattle:
                self.wait_and_tap_roi(self.load_roi("InterestBearing/reward"))
                self.scence = self.Scence.gameMap
                self.logger.info("确认退出战利品")
                continue
            if self.scence == self.Scence.onExitGame:
                if match := self.match_roi("InterestBearing/skipReport",
                                           screenshot=screen):
                    self.tap_rect(match.bbox)
                    self.logger.info("跳过报告")
                    continue
                if match := self.match_roi("InterestBearing/dailyMessage",
                                           screenshot=screen):
                    self.tap_rect(match.bbox)
                    self.logger.info("关闭日报")
                    continue
                if match := self.match_roi("InterestBearing/exitGameButton",
                                           screenshot=screen):
                    self.tap_rect(match.bbox)
                    self.logger.info("退出演算")
                    continue
                if match := self.match_roi("InterestBearing/giveUp",
                                           screenshot=screen):
                    self.scence = self.Scence.eventCover
                    self.step = self.Period.loopEnd
                    continue
