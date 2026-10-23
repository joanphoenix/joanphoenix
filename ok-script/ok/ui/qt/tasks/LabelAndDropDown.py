from PySide6.QtGui import QFontMetrics  # Needed for width calculation
from qfluentwidgets import ComboBox

from ok import og
from ok.ui.qt.common.design_system import control_width
from ok.ui.qt.tasks.ConfigLabelAndWidget import ConfigLabelAndWidget
from ok.util.collection import find_index_in_list


class LabelAndDropDown(ConfigLabelAndWidget):

    def __init__(self, config_desc, options, config, key: str):
        super().__init__(config_desc, config, key)
        self.key = key
        self.options = options
        self.tr_dict = {}
        self.tr_options = []
        for option in options:
            tr = og.app.tr(str(option))
            self.tr_options.append(tr)
            self.tr_dict[tr] = option

        self.combo_box = ComboBox()
        self.combo_box.addItems(self.tr_options)
        init_idx = find_index_in_list(options, self.config.get(self.key), 0)
        self.combo_box.setCurrentIndex(init_idx)

        fm = QFontMetrics(self.combo_box.font())
        max_width = 0
        for option in self.tr_options:
            # Measure text width
            max_width = max(max_width, fm.horizontalAdvance(option))

        self.combo_box.setFixedWidth(control_width(max_width + 50))

        self.combo_box.currentTextChanged.connect(self.text_changed)

        self.add_widget(self.combo_box, stretch=0)

    def text_changed(self, text):
        option = self.tr_dict.get(text)
        self.update_config(option)

    def update_value(self):
        val = self.config.get(self.key)
        tr = og.app.tr(str(val) if val is not None else "")
        idx = find_index_in_list(self.tr_options, tr, -1)
        if idx == -1:
            idx = find_index_in_list(self.options, val, 0)
        if idx != -1 and idx < len(self.tr_options):
            self.combo_box.setCurrentIndex(idx)
