import re
import cv2

from ok import Logger, find_color_rectangles
from src.task.DomainTask import DomainTask

logger = Logger.get_logger(__name__)

FORGERY_CHALLENGES = [
    "1 - Flaming Remnants (Metallic Drip / Sword)",
    "2 - Eroded Ruins (Waveworn Residue / Broadblade)",
    "3 - Marigold Woods (Cadence Seed / Pistol)",
    "4 - Moonlit Groves (Phlogiston / Gauntlet)",
    "5 - Misty Forest (Helix / Rectifier)",
    "6 - Mt. Firmament #6 (Metallic Drip / Sword)",
    "7 - Mt. Firmament #7 (Waveworn Residue / Broadblade)",
    "8 - Mt. Firmament #8 (Cadence Seed / Pistol)",
    "9 - Mt. Firmament #9 (Phlogiston / Gauntlet)",
    "10 - Mt. Firmament #10 (Helix / Rectifier)",
    "11 - Black Shores #11 (Metallic Drip / Sword)",
    "12 - Black Shores #12 (Waveworn Residue / Broadblade)",
    "13 - Black Shores #13 (Cadence Seed / Pistol)",
    "14 - Black Shores #14 (Phlogiston / Gauntlet)",
    "15 - Black Shores #15 (Helix / Rectifier)",
    "16 - Rinascita #16 (Metallic Drip / Sword)",
    "17 - Rinascita #17 (Waveworn Residue / Broadblade)",
    "18 - Rinascita #18 (Cadence Seed / Pistol)",
    "19 - Rinascita #19 (Phlogiston / Gauntlet)",
    "20 - Rinascita #20 (Helix / Rectifier)",
]


class ForgeryTask(DomainTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '⚒️ Forgery Challenge'
        self.description = 'Farms the selected Forgery Challenge. Must be able to teleport (F2).'
        self.support_schedule_task = True
        self.default_config = {
            'Which Forgery Challenge to Farm': FORGERY_CHALLENGES[0],
        }
        self.config_type['Which Forgery Challenge to Farm'] = {
            'type': 'drop_down',
            'options': FORGERY_CHALLENGES,
        }
        self.config_description = {
            'Which Forgery Challenge to Farm': 'Select the Forgery Challenge from the F2 list (1-20).',
        }
        self.stamina_once = 40
        self.structure = [5, 5, 5, 5]
        self.total_number = sum(self.structure)
        self.material_mat = None

    def run(self):
        super().run()
        self.make_sure_in_world()
        self.farm_forgery()

    def farm_forgery(self, daily=False, used_stamina=0, config=None):
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        if config is None:
            config = self.config
        raw_serial = config.get('Which Forgery Challenge to Farm', 1)
        if isinstance(raw_serial, str):
            match = re.search(r'\d+', raw_serial)
            serial = int(match.group(0)) if match else 1
        else:
            try:
                serial = int(raw_serial)
            except (ValueError, TypeError):
                serial = 1

        def teleport_once():
            self.teleport_into_domain(serial, daily)

        self.farm_domain_with_recovery_loop(must_use, teleport_once)

    def purification_material(self):
        self.send_key("esc")
        self.sleep(1)
        self.click_relative(0.62, 0.7)
        self.sleep(1)
        box = self.box_of_screen(243 / 2560, 162 / 1440, 928 / 2560, 559 / 1440, name='ascension_materials')
        self.draw_boxes(box.name, box)
        self.wait_book()
        if self.material_mat is not None and \
            (target := self.wait_until(lambda: self.find_one(template=self.material_mat, box=box, threshold=0.7), time_out=1)):
            self.click_box(target, after_sleep=1)
        self.click_relative(0.75, 0.90, after_sleep=1)
        self.ensure_main()

    def teleport_into_domain(self, serial_number, daily=False):
        self.open_boss_book('ningsu')
        self.info_set('Teleport to Forgery Challenge', serial_number - 1)
        if serial_number > self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(serial_number, self.total_number, self.structure)
        self.click(0.891, 0.910, after_sleep=1)
        self.click_team_challenge()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def get_material_mat(self):
        min_width = self.width_of_screen(80 / 2560)
        min_height = self.height_of_screen(80 / 1440)
        box = self.box_of_screen(2205 / 2560, 566 / 1440, 2357 / 2560, 984 / 1440)
        self.draw_boxes(box.name, box)
        material_boxes = find_color_rectangles(self.frame, material_box_color, min_width, min_height,
                                               box=box, threshold=0.6)
        if material_boxes:
            box_start = self.width_of_screen(20 / 2560)
            box_len = self.width_of_screen(90 / 2560)
            target = min(material_boxes, key=lambda box: box.y)
            logger.info(f"Found {len(material_boxes)} material boxes, selected target at y={target.y}")
            mat_box = target.copy(box_start, box_start, box_len - target.width, box_len - target.height, 'material_mat')
            self.draw_boxes(mat_box.name, mat_box)
            self.material_mat = cv2.resize(mat_box.crop_frame(self.frame), None,
                                           fx=1.1, fy=1.1, interpolation=cv2.INTER_LINEAR)


material_box_color = {
    'r': (45, 75),  # Red range
    'g': (45, 75),  # Green range
    'b': (45, 75)  # Blue range
}
