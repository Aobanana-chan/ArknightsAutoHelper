import time
import numpy as np
import cv2

from Arknights.addons.common import CommonAddon
from automator import AddonBase
from imgreco import imgops, resources, ocr
import util.cvimage as Image
from util.cvimage import Rect

operator_alphabet = '切慕草早维牙火崖帕HE莉桃白刀鸮临空(灰幽耶柏)日者杰葬刻默怀芬地罗巡棘绮微初箱F糖棉娘尼有莱薄消普安恋L赛达哈槐清'+ \
    '格陨史心水毫翎讯稀登银能惊琴苗M锡宾林近骑古温傀煌l-野琳守俄蓉伦利因梓夫蒂熔雨a炎峰禾凯劳毛义霜1雪汀蜜道玫弦米山砾洛异菈'+ \
    '爆柳波诗嘉魔奥威峨西食乌3恩娅莓末特露丝客希丽铁马风正烟砂角良泥刺狮月塞击旺境喙香灵屠夕石极见号喉星雅华C哲歌云絮泉赫泡深杜蜡'+ \
    'e蚺车2丸龙蕾颂芙冬都陈克桑黑X刃法蜂莫黛雷苇莺铃琥药萨n点焰宴暴缇苏舌莎行燧塔卡叶慑使陀芳伊拜瑕坚贝真c蓝兽鲨斯蝎涅浊'+ \
    '丁娜调战嵯影鲁进提尾吽罪笔兰布之面年猎耀假迭红闪迷绿凛远阿暗鬃断洁笛天卫葚夜W熊松烬巫果德音流蛇爱酸靛铸图神理森羽艾推t尔梅s斑麦四索拉光T知王海毒送贾亚蛰鞭R可狱赤岩金雉蚀师士色孑人比苦豆缠'

layout_template = {
    'control_center': (516, 9, 786, 144),
    'meeting_room': (820, 77, 1022, 144),

    'B101':(76.5, 144.5, 210.5, 211),
    'B102':(211.75, 144.5, 345.75, 211),
    'B103':(347, 144.5, 481, 211),
    'dorm1':(516, 144.5, 718, 211),
    'processing':(887, 144.5, 1022, 211),

    'B201':(9, 212, 144, 278.5),
    'B202':(144, 212, 279, 278.5),
    'B203':(280, 212, 414, 278.5),
    'dorm2':(583, 212, 786, 278.5),
    'office':(887, 212, 1022, 278.5),

    'B301':(77, 279.5, 211, 346),
    'B302':(212, 279.5, 346, 346),
    'B303':(347, 279.5, 481, 346),
    'dorm3':(516, 279.5, 718, 346),
    'training':(887, 279.5, 1022, 346),

    'dorm4':(583, 347, 785, 414)
}

def transform_rect(rc, M):
    l, t, r, b = rc
    pts = np.asarray([l,t, r,t, r,b, l,b], dtype=np.float32).reshape(-1, 1, 2)
    tpts: np.ndarray = cv2.transform(pts, M).reshape(-1, 2)
    left = int(round(tpts[:, 0].min()))
    top = int(round(tpts[:, 1].min()))
    right = int(round(tpts[:, 0].max()))
    bottom = int(round(tpts[:, 1].max()))
    return left, top, right, bottom

class RIICAddon(AddonBase):
    def on_attach(self) -> None:
        self.ocr = ocr.acquire_engine_global_cached('zh-cn')
        self.register_cli_command('riic', self.cli_riic, self.cli_riic.__doc__)
    
    def check_in_riic(self, screenshot=None):
        if self.match_roi('riic/overview', screenshot=screenshot):
            return True
        if roi := self.match_roi('riic/pending', screenshot=screenshot):
            self.logger.info('取消待办事项')
            self.tap_rect(roi.bbox)
            return True
        return False

    def enter_riic(self):
        self.addon(CommonAddon).back_to_main(extra_predicate=self.check_in_riic)
        if self.check_in_riic():
            return
        result = self.match_roi('riic/riic_entry', fixed_position=False, method='sift', mode='L')
        if result:
            self.logger.info('进入基建')
            self.tap_quadrilateral(result.context.template_corners, post_delay=6)
        else:
            raise RuntimeError('failed to find riic entry')
        while not self.check_in_riic():
            self.delay(1)
        self.logger.info('已进入基建')
        
    def collect_all(self):
        self.enter_riic()
        count = 0
        while count < 2:
            if roi := (self.match_roi('riic/notification', fixed_position=False, method='template_matching') or
                       self.match_roi('riic/dark_notification', fixed_position=False, method='template_matching')):
                while True:
                    self.logger.info('发现蓝色通知')
                    self.tap_rect(roi.bbox)
                    if self.match_roi('riic/pending'):
                        break
                    self.logger.info('重试点击蓝色通知')
                while roi := self.wait_for_roi('riic/collect_all', timeout=2, fixed_position=False, method='template_matching'):
                    self.logger.info('发现全部收取按钮')
                    rc = roi.bbox
                    rc.y = 93.704 * self.vh
                    rc.height = 5.833 * self.vh
                    rc.x -= 7.407 * self.vh
                    self.tap_rect(roi.bbox)
                break
            else:
                self.logger.info('未发现蓝色通知，等待 3 s')
                self.delay(3)
                count += 1
        self.logger.info('一键收取完成')

    def recognize_layout(self):
        self.enter_riic()
        self.logger.info('正在识别基建布局')
        screenshot = self.device.screenshot()
        
        t0 = time.monotonic()
        # screen_mask = None
        templ_mask = resources.load_image_cached('riic/layout.mask.png', 'L').array
        left_mask = imgops.scale_to_height(resources.load_image_cached('riic/layout.screen_mask.left.png', 'L'), screenshot.height, Image.NEAREST)
        right_mask = imgops.scale_to_height(resources.load_image_cached('riic/layout.screen_mask.right.png', 'L'), screenshot.height, Image.NEAREST)
        screen_mask = np.concatenate([left_mask.array, np.full((screenshot.height, screenshot.width - left_mask.width - right_mask.width), 255, dtype=np.uint8), right_mask.array], axis=1)
        match = imgops.match_feature_orb(resources.load_image_cached('riic/layout.png', 'L'), screenshot.convert('L'), templ_mask=templ_mask, haystack_mask=screen_mask, limited_transform=True)
        # roi = self.match_roi('riic/layout', fixed_position=False, method='sift', mode='L')
        self.logger.debug('%r', match)
        if match.M is None:
            raise RuntimeError('未能识别基建布局')
        # discard rotation
        M = match.M
        scalex = np.sqrt(M[0,0] ** 2 + M[0,1] ** 2)
        scaley = np.sqrt(M[1,0] ** 2 + M[1,1] ** 2)
        translatex = M[0,2]
        translatey = M[1,2]
        scale = (scalex+scaley)/2
        M = np.array([[scale, 0, translatex],[0, scale, translatey]])
        print('M=', M)
        layout = {
            name: transform_rect(rect, M)
            for name, rect in layout_template.items()
        }
        t1 = time.monotonic()
        print('time elapsed:', t1-t0)
        image = screenshot.convert('native')

        for name, rect in layout.items():
            cv2.rectangle(image.array, Rect.from_ltrb(*rect).xywh, [0, 0, 255], 1)
            cv2.putText(image.array, name, [rect[0]+2, rect[3]-2], cv2.FONT_HERSHEY_PLAIN, 2, [0,0,255], 2)

        image.show()
        print(layout)

    def recognize_operator_select(self, recognize_skill=False):
        if not (roi := self.match_roi('riic/clear_selection')):
            raise RuntimeError('not here')
        self.tap_rect(roi.bbox)
        screenshot = imgops.scale_to_height(self.device.screenshot().convert('RGB'), 1080)
        dbg_screen = screenshot.copy()
        xs = []
        operators = []
        cropim = screenshot.array[485:485+37]
        cropim = cv2.cvtColor(cropim, cv2.COLOR_RGB2GRAY)
        thim = cv2.threshold(cropim, 64, 1, cv2.THRESH_BINARY)[1]
        ysum = np.sum(thim, axis=0).astype(np.int16)
        ysumdiff=np.diff(ysum)
        row1xs = np.where(ysumdiff<=ysumdiff.min()+3)[0] + 1

        for x in row1xs:
            if x < 605 or x + 184 > screenshot.width:
                continue
            rc = Rect.from_xywh(x, 113, 184, 411)
            operators.append((screenshot.subview(rc), rc))

        cropim = screenshot.array[909:909+36]
        cropim = cv2.cvtColor(cropim, cv2.COLOR_RGB2GRAY)
        thim = cv2.threshold(cropim, 64, 1, cv2.THRESH_BINARY)[1]
        ysum = np.sum(thim, axis=0).astype(np.int16)
        ysumdiff=np.diff(ysum)
        row2xs = np.where(ysumdiff<=ysumdiff.min()+3)[0] + 1

        for x in row2xs:
            if x < 605 or x + 184 > screenshot.width:
                continue
            rc = Rect.from_xywh(x, 534, 184, 411)
            operators.append((screenshot.subview(rc), rc))

        # for color in ('green', 'yellow', 'red'):
        #     face = resources.load_image_cached(f'riic/{color}_face.png', 'RGB')
        #     w, h = face.size
        #     res = cv2.matchTemplate(screenshot.array, face.array, cv2.TM_CCOEFF_NORMED)
        #     while True:
        #         min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        #         if max_val > 0.9:
        #             xs.append(max_loc[0] - 14)
        #             res[max_loc[1]-h//2:max_loc[1]+h//2+1, max_loc[0]-w//2:max_loc[0]+w//2+1] = 0
        #             operators.append(screenshot.subview((max_loc[0] - 14, max_loc[1] - 345, max_loc[0] + 170, max_loc[1] + 66)))
        #         else:
        #             break
        for o, rc in operators:
            cv2.rectangle(dbg_screen.array, rc.xywh, [255,0,0, 1])
        self.richlogger.logimage(dbg_screen)
        for o, rc in operators:
            self.richlogger.logimage(o)
            self.recognize_operator_box(o, recognize_skill)

        # xs = np.array(xs)
        # xs.sort()
        # diffs = np.diff(xs)

        # dedup_xs = xs[np.concatenate(([183], diffs)) > 5]
        # for x in dedup_xs:
        #     cv2.line(dbg_screen.array, (x,0), (x,screenshot.height), [255,0,0], 1)
        # dbg_screen.show()

    def recognize_operator_box(self, img: Image.Image, recognize_skill=False):
        name_img =  imgops.enhance_contrast(img.subview((0, 375, img.width, img.height)).convert('L'), 90, 220)
        name_img = Image.fromarray(255 - name_img.array)
        name = self.ocr.recognize(name_img, ppi=240, hints=[ocr.OcrHint.SINGLE_LINE], char_whitelist=operator_alphabet)
        mood_img = img.subview(Rect.from_xywh(44, 358, 127, 3)).convert('L').array
        mood_img = np.max(mood_img, axis=0)
        mask = (mood_img >= 200).astype(np.uint8)
        mood = np.count_nonzero(mask) / mask.shape[0]

        tagimg = img.subview((35, 209, 155, 262))
        on_shift = resources.load_image_cached('riic/on_shift.png', 'RGB')
        distracted = resources.load_image_cached('riic/distracted.png', 'RGB')
        rest = resources.load_image_cached('riic/rest.png', 'RGB')
        tag = None
        if imgops.compare_mse(tagimg, on_shift) < 3251:
            tag = 'on_shift'
        elif imgops.compare_mse(tagimg, distracted) < 3251:
            tag = 'distracted'
        elif imgops.compare_mse(tagimg, rest) < 3251:
            tag = 'rest'
        
        if tag:
            room_img = img.subview(Rect.from_xywh(42, 6, 74, 30)).array
            room_img = imgops.enhance_contrast(Image.fromarray(np.max(room_img, axis=2)), 64, 220)
            room_img = Image.fromarray(255 - room_img.array)
            self.richlogger.logimage(room_img)
            room = self.ocr.recognize(room_img, ppi=240, hints=[ocr.OcrHint.SINGLE_LINE], char_whitelist='0123456789FB')
        else:
            room = None

        if recognize_skill:
            skill1_icon = img.subview(Rect.from_xywh(4,285,54,54))
            skill2_icon = img.subview(Rect.from_xywh(67,285,54,54))
            skill1, score1 = self.recognize_skill(skill1_icon)
            skill2, score2 = self.recognize_skill(skill2_icon)
        else:
            skill1 = None
            skill2 = None

        self.richlogger.logimage(name_img)
        self.richlogger.logtext(repr((name, mood*24, room, tag, skill1, skill2)))
        print(name, mood*24, room, tag, skill1, skill2, sep='\t')

    def recognize_skill(self, icon) -> tuple[str, float]:
        self.richlogger.logimage(icon)
        if np.count_nonzero(icon.array > 100) < 10:
            self.richlogger.logtext('no skill')
            return None, 0
        from . import bskill_cache
        icon = icon.resize(bskill_cache.icon_size)
        normal_comparisons = [(name, imgops.compare_mse(icon, template)) for name, template in bskill_cache.normal_icons.items()]
        normal_comparisons.sort(key=lambda x: x[1])

        result = normal_comparisons[0]
        if result[1] > 1000:
            dark_comparisons = [(name, imgops.compare_mse(icon, template)) for name, template in bskill_cache.dark_icons.items()]
            dark_comparisons.sort(key=lambda x: x[1])

            if dark_comparisons[0][1] < normal_comparisons[0][1]:
                result = dark_comparisons[0]

        if result[1] > 1000:
            self.richlogger.logtext('no match')
            return None, 0

        self.richlogger.logtext(f'matched {result[0]} with mse {result[1]}')

        return result

    def cli_riic(self, argv):
        """
        riic <subcommand>
        基建功能（开发中）
        riic collect
        收取制造站及贸易站
        """
        if len(argv) == 1:
            print("usage: riic <subcommand>")
            return 1
        cmd = argv[1]
        if cmd == 'collect':
            self.collect_all()
            return 0
        elif cmd == 'debug':
            t0 = time.monotonic()
            self.recognize_operator_select(recognize_skill=True)
            t1 = time.monotonic()
            print("time elapsed:", t1-t0)
            t0 = time.monotonic()
            self.recognize_operator_select(recognize_skill=True)
            t1 = time.monotonic()
            print("time elapsed:", t1-t0)
        else:
            print("unknown command:", cmd)
            return 1
