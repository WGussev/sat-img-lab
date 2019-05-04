from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
QHBoxLayout, QGridLayout, QAction, QFileDialog, QSlider, QSizeGrip,
QFrame, QRadioButton, QButtonGroup, QComboBox, QInputDialog)
from PyQt5.QtGui import QPixmap, QCursor, QImage
from PyQt5.QtCore import pyqtSignal, Qt
import sys
import os
from imageio import imread, imwrite
import tempfile
from numpy import uint8, ones
from collections import namedtuple

from pathlib import Path

import cv2
import numpy 
import matplotlib.pyplot as plt

# needed to pass selected point coordinates to the cv2.floodFill()
Point = namedtuple('Point', 'x, y')

class Canvas(QLabel):

    """ Allows relative position tracking  within an image."""

    pressed = pyqtSignal(int, int)

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlag(Qt.SubWindow)
        self.setMouseTracking(True)

    def mousePressEvent(self, e):
        x_max = self.width()
        y_max = self.height()
        # if the cursor is within the image (label)        
        if (e.x() <= x_max) and (e.y() <= y_max):
            self.pressed.emit(e.x(), e.y())


class myGUI(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):

        self._wand_enabled = False

        self._mask_type = numpy.zeros((258, 258), dtype=uint8)
        self._mask = numpy.zeros((258, 258), dtype=uint8)

        self._toggled = False

        self._x2_pressed = False

        self._x_scale = 2
        self._y_scale = 2

        self._x = 0
        self._y = 0

        self.tile_cash = []
        # create and initialize image canvas
        self.cnv_img = Canvas(self)

        pixm = QPixmap('plug.jpg')
        self.img = imread('plug.jpg')
        #self.img = self.img.astype(uint8)
        self.cnv_img.setPixmap(pixm)
        #
        self.cnv_msk = Canvas(self)
        self.cnv_msk.setPixmap(pixm)
        #
        self.btn_open = QPushButton('Open Directory', self)
        self.btn_new_mask = QPushButton('New Mask', self)
        self.btn_add = QPushButton('Add Selection', self)
        self.btn_save_mask = QPushButton('Save Mask', self)
        # self.btn_scale = QPushButton('Scale: x2', self)
        self.btn_next = QPushButton('Next', self)
        self.btn_prev = QPushButton('Previuos', self)
        self.btn_subtract = QPushButton('Subtract Selection', self)
        self.btn_new_mask.setDisabled(True)
        self.btn_add.setDisabled(True)
        self.btn_subtract.setDisabled(True)
        self.btn_save_mask.setDisabled(True)
        # self.btn_scale.setDisabled(True)
        self.btn_next.setDisabled(True)
        self.btn_prev.setDisabled(True)
        #
        self.cnv_img_info = QLabel(self)

        self._ih = pixm.height()
        self._iw = pixm.width()

        self.sld = QSlider(Qt.Horizontal, self)
        self.sld.setFixedSize(500, 30)
        self.sld.setMaximum(255)
        self.sld.setMinimum(0)
        self.sld.setValue(20)
        self.sld.setTickPosition(QSlider.TicksBelow)
        self.sld.setTickInterval(10)
        
        grid = QGridLayout()
        grid.addWidget(self.cnv_img, 0, 0, 6, 1, Qt.AlignCenter)
        grid.addWidget(self.sld, 6, 0, Qt.AlignCenter)

        grid.addWidget(self.cnv_msk, 0, 1, 6, 1, Qt.AlignCenter)

        grid.addWidget(self.btn_open, 0, 2, 1, 2, Qt.AlignVCenter)
        grid.addWidget(self.btn_new_mask, 1, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.cnv_img_info, 2, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.btn_add, 3, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.btn_subtract, 4, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.btn_save_mask, 5, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.btn_prev, 6, 2, Qt.AlignVCenter)
        grid.addWidget(self.btn_next, 6, 3, Qt.AlignVCenter)

        
        self.setLayout(grid)

        self.cnv_img.pressed.connect(self.magic_wand)
        # btn_open opens a dialogue for selecting a directory
        # containing the images to label.
        self.btn_open.pressed.connect(self.showDialog)
        # btn_next opens the next image from the directory.
        self.btn_next.pressed.connect(self.open_next_file)
        self.btn_prev.pressed.connect(self.open_previous_file)
        # sld controls the FloodFill threshold value
        self.sld.valueChanged.connect(self.change_thresh)
        #
        self.btn_subtract.pressed.connect(lambda: self.subtract_masks(self._mask_type, self._mask))
        # self.btn_scale.pressed.connect(self.x2)
        #
        self.btn_new_mask.pressed.connect(self.get_type)
        self.btn_new_mask.pressed.connect(self.create_mask_type)
        #
        self.btn_add.pressed.connect(lambda: self.combine_masks(self._mask_type, self._mask))
        #
        self.btn_save_mask.pressed.connect(self.save_mask)
        #
        self.show()
    
    def showDialog(self):

        """ Open directory selection dialogue"""

        self.dir_path = QFileDialog.getExistingDirectoryUrl(self).path()

        if self.dir_path:
            self.tiles_list = os.listdir(str(self.dir_path))
            self.btn_prev.setDisabled(False)
            self.btn_next.setDisabled(False)
            self._tile_number = 0


    def open_file(self):

        """ Open the next tif file from the chosen directory.
            The .tif file is opened - saved as jpg (by ) - and reopened as jpg.
        """
        self._wand_enabled = False

        self.tile_info = {'file': '', 'layer': '', }
        self.create_mask_type()

        self.btn_new_mask.setDisabled(False)
        self.btn_add.setDisabled(True)
        self.btn_subtract.setDisabled(True)        

        self._x_scale = 2
        self._y_scale = 2
        self._x2_pressed = False

        self._tile_name = self.tiles_list[self._tile_number]
        self.tile_info['file']  = self._tile_name
        self.cnv_img_info.setText('\n'.join([': '.join(i) for i in self.tile_info.items()]))
        path = Path(self.dir_path, self._tile_name)      
        self.img = imread(path)
        print(self.img.shape)
        self._qimg = QImage(self.img.data, self.img.shape[1], self.img.shape[0], self.img.strides[0], QImage.Format_RGB888)

        pixm = QPixmap(self._qimg)
        self.cnv_img.setPixmap(pixm.scaled(self.img.shape[1] * self._x_scale, self.img.shape[0]*self._y_scale, Qt.KeepAspectRatio))

        self._ih = pixm.height()
        self._iw = pixm.width()

    def open_previous_file(self):
        self._tile_number -= 1
        self.open_file()

    def open_next_file(self):
        self._tile_number += 1
        self.open_file()

    def change_thresh(self, thresh):
        self.magic_wand(self._x * self._x_scale, self._y * self._y_scale, thresh)

    def magic_wand(self, x, y, thresh=25):

        """Choose a connected component and show the chosen region"""

        # enable the magic wand tool only if a surface type for the mask is selected

        if self._wand_enabled == False:
            return None

        # move slider to the initial position
        self.sld.setValue(thresh)
        # change seedPoint coordinates
        self._x = x // self._x_scale
        self._y = y // self._y_scale      
        seedPoint = Point(self._x, self._y)
        # number of neighbour pixels considered | value to fill the mask
        flags = 4 | (1 << 8)
        # compare considered points to the seed | do not change the pic itself
        flags |= cv2.FLOODFILL_FIXED_RANGE |  cv2.FLOODFILL_MASK_ONLY
        self._mask = numpy.zeros((self._ih+2, self._iw+2), dtype=uint8)
        # changes the mask inplace
        cv2.floodFill(self.img, self._mask, seedPoint, 0, (thresh,)*3, (thresh,)*3, flags)
        # contours to represent the type mask
        contours_type, _ = cv2.findContours(self._mask_type[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        draw_type = cv2.drawContours(self.img.copy(), contours_type, -1, (0, 128, 128), 1)
        # contours to represent the current selection
        contours_selection, _ = cv2.findContours(self._mask[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        draw_selection = cv2.drawContours(draw_type.copy(), contours_selection, -1, (128, 128, 0), 1)
        # display both selections
        applied_mask_1 = QImage(draw_selection.data, draw_selection.shape[1], draw_selection.shape[0], draw_selection.strides[0], QImage.Format_RGB888)
        pixm = QPixmap(applied_mask_1)
        self.cnv_img.setPixmap(pixm.scaled(self.cnv_img.pixmap().width(),self.cnv_img.pixmap().height(), Qt.KeepAspectRatio))

    def x2(self):

        # toggle between x2-enlarged and real-size image

        pixm = self.cnv_img.pixmap()
        y = self.cnv_img.pixmap().height()
        x = self.cnv_img.pixmap().width()

        if self._x2_pressed == True:
            self.cnv_img.setPixmap(pixm.scaled(x // 2, y // 2, Qt.KeepAspectRatio))
            self._x_scale = self._x_scale // 2
            self._y_scale = self._y_scale // 2
            self._x2_pressed = False
        else:
            self.cnv_img.setPixmap(pixm.scaled(x * 2, y * 2, Qt.KeepAspectRatio))
            self._x_scale = self._x_scale * 2
            self._y_scale = self._y_scale * 2
            self._x2_pressed = True


    def save_mask(self):
        if not os.path.isdir('./masks'):
            os.mkdir('./masks')
        path = './masks/' + self._tile_name.split('.')[0] + '_' + self._surface_type + '.bmp'
        imwrite(path, self._mask_type[1:-1, 1:-1]*255, format='bmp')

    def combine_masks(self, mask_1, mask_2):
        # works in place (mask_1)
        mask_1 |= (mask_2 == 1)
        self.show_type_mask()

    def subtract_masks(self, mask_1, mask_2):

        mask_1 &= (mask_2 != 1)
        self.show_type_mask()

    def create_mask_type(self):

        self._mask_type = numpy.zeros((self._ih+2, self._iw+2), dtype=uint8)
        self.show_type_mask()

    def show_type_mask(self):

        test = self._mask_type * 255
        type_mask = QImage(test.data, test.shape[1], test.shape[0], test.strides[0], QImage.Format_Grayscale8)
        pixm_mask = QPixmap(type_mask)
        self.cnv_msk.setPixmap(pixm_mask.scaled(self.cnv_img.pixmap().width(),self.cnv_img.pixmap().height(), Qt.KeepAspectRatio))

    def get_type(self):
        items = ('river', 'lake', 'road', 'building', 'firebreak', 'cloud', 'cloud shadow')
                
        item, ok = QInputDialog.getItem(self, "select input dialog", 
            "surface types", items, 0, False)
                
        if ok and item:
            self.btn_add.setDisabled(False)
            self.btn_subtract.setDisabled(False)
            self.btn_save_mask.setDisabled(False)
            self.tile_info['layer'] = item
            self.cnv_img_info.setText('\n'.join([': '.join(i) for i in self.tile_info.items()]))
            self._surface_type = item
            self._wand_enabled = True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = myGUI()
    sys.exit(app.exec_())
