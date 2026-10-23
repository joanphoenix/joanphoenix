import re
from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)

TACET_SUPPRESSIONS = [
    "1 - Desorock Highland (Sun-sinking Eclipse / Celestial Light)",
    "2 - Central Plains (Sierra Gale / Molten Rift)",
    "3 - Port City of Guixu (Molten Rift / Sun-sinking Eclipse)",
    "4 - Whining Aix's Mire (Void Thunder / Celestial Light)",
    "5 - Tiger's Maw (Freezing Frost / Molten Rift)",
    "6 - Dim Forest (Sierra Gale / Void Thunder)",
    "7 - Wuming Bay (Freezing Frost / Sierra Gale)",
    "8 - Norfall Barrens (Sun-sinking Eclipse / Void Thunder)",
    "9 - Central Plains II (Freezing Frost / Celestial Light)",
    "10 - Mt. Firmament: Frostlands (Celestial Light / Freezing Frost)",
    "11 - Mt. Firmament: Luminous (Sun-sinking Eclipse / Sierra Gale)",
    "12 - Mt. Firmament: Memento (Void Thunder / Molten Rift)",
    "13 - Black Shores #13",
    "14 - Black Shores #14",
    "15 - Black Shores #15",
    "16 - Rinascita #16",
    "17 - Rinascita #17",
    "18 - Rinascita #18",
    "19 - Rinascita #19",
    "20 - Rinascita #20",
    "21 - Rinascita #21",
]


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Farms the selected Tacet Suppression, until no stamina. Must be able to teleport (F2)."
        self.name = "🌊 Tacet Suppression"
        self.support_schedule_task = True
        self.structure = [4, 5, 5, 7]
        self.total_number = sum(self.structure)
        self.target_enemy_time_out = 10
        self.default_config = {
            'Which Tacet Suppression to Farm': TACET_SUPPRESSIONS[0],
        }
        self.config_type['Which Tacet Suppression to Farm'] = {
            'type': 'drop_down',
            'options': TACET_SUPPRESSIONS,
        }
        self.config_description = {
            'Which Tacet Suppression to Farm': 'Select the Tacet Suppression from the F2 list (1-21).',
        }
        self.door_walk_method = {  # starts with 0
            0: [],
            1: [],
            2: [],
            3: [],
            4: [],
            5: [],
            6: [],
            7: [],
            8: [],
            9: [["a", 0.3]],
            10: [["d", 0.6]],
            11: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }
        self.stamina_once = 60

    def run(self):
        super().run()
        self.ensure_main(time_out=180)
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self, daily=False, used_stamina=0, config=None, max_recovery_retries=3):
        if config is None:
            config = self.config
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        self.info_incr('used stamina', 0)
        recovery_retries = 0
        self.realm_entry_at_heal_point = False
        while True:
            self.sleep(1)
            self.openF2Book("gray_book_boss")
            current, back_up, total = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up, total = self.get_stamina()
            if total < self.stamina_once:
                return self.not_enough_stamina()

            self.open_boss_book('wuyin')
            raw_target = config.get('Which Tacet Suppression to Farm', 1)
            if isinstance(raw_target, str):
                match = re.search(r'\d+', raw_target)
                index = (int(match.group(0)) - 1) if match else 0
            else:
                try:
                    index = int(raw_target) - 1
                except (ValueError, TypeError):
                    index = 0
            self.teleport_to_tacet(index)
            self.click_team_challenge()
            while True:
                self.wait_in_team_and_world(time_out=120)
                try:
                    self.combat_once(target=True)
                except CharRevivedException:
                    recovery_retries += 1
                    if recovery_retries >= max_recovery_retries:
                        self.log_info(f'farm_tacet: exceeded recovery retries ({max_recovery_retries}), stop farming',
                                      notify=True)
                        return None
                    self.log_info('farm_tacet: death recovered, re-enter from F2 book')
                    self.realm_entry_at_heal_point = True  # 恢复后站在信标上, 从 F2 直接进本
                    break
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
                self.sleep(2)
                if not self.has_claim_stamina():
                    self.esc_cancel()
                    self.log_info('is not claim treasure, restart challenge')
                    continue
                can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
                self.info_incr('used stamina', used)
                self.sleep(4)
                if not can_continue:
                    self.click_relative(0.365, 0.853, hcenter=True)
                    self.wait_in_team_and_world(time_out=120)
                    return None
                else:
                    self.click_relative(0.640, 0.851, hcenter=True, after_sleep=0.2)
                    self.wait_click_skip_dialog_confirm()
                must_use -= used

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        return self.click_on_book_target(index + 1, self.total_number, self.structure)
