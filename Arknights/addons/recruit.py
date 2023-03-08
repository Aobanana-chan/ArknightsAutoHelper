from automator import AddonBase, cli_command


class RecruitAddon(AddonBase):

    def selectMax(self, result) -> tuple:
        maxrank = 0
        maxtag = ()
        for tags, operators, rank in result:
            if rank > maxrank:
                maxtag = tags
                maxrank = rank
        return maxtag

    def auto_recruit(self, count: int):
        import imgreco.recruit
        for _ in range(count):
            # 开始招募
            self.wait_and_tap_roi(self.load_roi("autoRecruit/start"))
            # 拉满时间
            self.delay(1)
            self.tap_rect((570, 411.00000000000006, 780, 477))
            # 识别
            with self.helper.frontend.context:
                result = self.recruit()
            tags = self.selectMax(result)
            print("选择标签:", tags)
            tag_with_pos = imgreco.recruit.get_recruit_tags_with_position(
                self.screenshot())
            # 选中tag
            for tag, position in tag_with_pos:
                if tag in tags:
                    self.tap_rect(position)

            # 确定
            self.tap_rect((1328, 837, 1608, 902))

            # 加速
            print("立即招募")
            self.wait_and_tap_roi(self.load_roi("autoRecruit/get"))
            self.delay(1)
            self.tap_rect((962, 705, 1894, 813))
            # 获得
            print("招募")
            self.wait_and_tap_roi(self.load_roi("autoRecruit/got"))
            self.delay(3)
            print("跳过")
            self.wait_and_tap_roi(self.load_roi("autoRecruit/skip"))
            self.delay(3)
            while True:
                self.tap_rect((945, 654, 979, 684))
                try:
                    self.wait_for_roi("autoRecruit/start")
                    break
                except:
                    continue

    def recruit(self):
        import imgreco.recruit
        from . import recruit_calc
        self.logger.info('识别招募标签')
        tags = imgreco.recruit.get_recruit_tags(self.screenshot())
        self.logger.info('可选标签：%s', ' '.join(tags))
        if len(tags) != 5:
            self.logger.warning('识别到的标签数量异常，一共识别了%d个标签', len(tags))
        result = recruit_calc.calculate(tags)
        self.logger.debug('计算结果：%s', repr(result))
        return result

    @cli_command('recruit')
    def cli_recruit(self, argv):
        """
        recruit [tags ...]
        recruit auto [count] 指定count次数的自动招募
        公开招募识别/计算，不指定标签则从截图中识别
        """
        from . import recruit_calc

        if 2 <= len(argv) <= 6:
            if argv[1] == "auto":
                self.auto_recruit(int(argv[2]))
            else:
                tags = argv[1:]
                result = recruit_calc.calculate(tags)
        elif len(argv) == 1:
            with self.helper.frontend.context:
                result = self.recruit()
        else:
            print('要素过多')
            return 1

        colors = [
            '\033[36m', '\033[90m', '\033[37m', '\033[32m', '\033[93m',
            '\033[91m'
        ]
        reset = '\033[39m'
        for tags, operators, rank in result:
            taglist = ','.join(tags)
            if rank >= 1:
                taglist = '\033[96m' + taglist + '\033[39m'
            print("%s: %s" % (taglist, ' '.join(colors[op[1]] + op[0] + reset
                                                for op in operators)))
