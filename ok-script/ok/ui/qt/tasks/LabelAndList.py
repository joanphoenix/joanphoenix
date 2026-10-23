from qfluentwidgets import SpinBox

from ok.ui.qt.tasks.ConfigLabelAndWidget import ConfigLabelAndWidget
from ok.ui.qt.tasks.LabelAndSpinBox import fix_spinbox_layout


class LabelAndDoubleSpinBox(ConfigLabelAndWidget):

    def __init__(self, config, config_desc, key: str):
        super().__init__(config_desc, key)
        self.key = key
        self.config = config
        self.spin_box = SpinBox()
        self.spin_box.setValue(self.config[self.key])
        self.spin_box.valueChanged.connect(self.value_changed)
        self.add_widget(self.spin_box)
        fix_spinbox_layout(self.spin_box)

    def value_changed(self, value):
        self.config[self.key] = value
