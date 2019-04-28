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

# surface types: river, lake (body of water), road, building, firebreak, cloud, cloud shade

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

        self._mask_type = numpy.zeros((258, 258), dtype=uint8)
        self._mask = numpy.zeros((258, 258), dtype=uint8)

        self._toggled = False

        self._x2_pressed = False

        self._x_scale = 1
        self._y_scale = 1

        self._x = 0
        self._y = 0

        self.tile_cash = []
        # create and initialize image canvas
        self.lbl = Canvas(self)

        pixm = QPixmap('plug.jpg')
        self.img = imread('plug.jpg')
        self.img = self.img.astype(uint8)
        self.lbl.setPixmap(pixm)
        #
        self.btn_open = QPushButton('Open Directory', self)
        self.btn_new_mask = QPushButton('New Mask', self)
        self.btn_update_mask = QPushButton('Update Mask', self)
        self.btn_save_mask = QPushButton('Save Mask', self)
        self.btn_scale = QPushButton('Scale: x2', self)
        self.btn_next = QPushButton('Next', self)
        
        self.btn_new_mask.setDisabled(True)
        self.btn_update_mask.setDisabled(True)
        self.btn_save_mask.setDisabled(True)
        self.btn_scale.setDisabled(True)
        self.btn_next.setDisabled(True)
        #
        self.lbl_type = QLabel(self)

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
        grid.addWidget(self.lbl, 0, 0, 6, 1, Qt.AlignCenter)
        grid.addWidget(self.sld, 6, 0, Qt.AlignCenter)
        grid.addWidget(self.btn_open, 0, 1, Qt.AlignVCenter)
        grid.addWidget(self.btn_new_mask, 1, 1, Qt.AlignVCenter)
        grid.addWidget(self.lbl_type, 2, 1, Qt.AlignVCenter)
        grid.addWidget(self.btn_update_mask, 3, 1, Qt.AlignVCenter)
        grid.addWidget(self.btn_save_mask, 4, 1, Qt.AlignVCenter)
        grid.addWidget(self.btn_scale, 5, 1, Qt.AlignVCenter)
        grid.addWidget(self.btn_next, 6, 1, Qt.AlignVCenter)
        
        self.setLayout(grid)

        self.lbl.pressed.connect(self.magic_wand)
        # btn_open opens a dialogue for selecting a directory
        # containing the images to label.
        self.btn_open.pressed.connect(self.showDialog)
        # btn_next opens the next image from the directory.
        self.btn_next.pressed.connect(self.open_file)
        # sld controls the FloodFill threshold value
        self.sld.valueChanged.connect(self.change_thresh)
        #
        self.btn_scale.pressed.connect(self.x2)
        #
        self._save_flag = 0
        #
        self.btn_new_mask.pressed.connect(self.get_type)
        self.btn_new_mask.pressed.connect(self.create_mask_type)
        #
        self.btn_update_mask.pressed.connect(lambda: self.combine_masks(self._mask_type, self._mask))
        #
        self.btn_save_mask.pressed.connect(self.save_mask)
        #
        self.show()
    
    def showDialog(self):

        """ Open directory selection dialogue"""

        self.dir_path = QFileDialog.getExistingDirectoryUrl(self).path()

        if self.dir_path:
            self.tiles_list = os.listdir(str(self.dir_path))
            self.btn_next.setDisabled(False)

    def open_file(self):

        """ Open the next tif file from the chosen directory.
            The .tif file is opened - saved as jpg (by ) - and reopened as jpg.
        """

        self.btn_new_mask.setDisabled(False)
        self.btn_scale.setDisabled(False)

        self._x_scale = 1
        self._y_scale = 1
        self._x2_pressed = False

        self._tile_name = self.tiles_list.pop()
        path = Path(self.dir_path, self._tile_name)      
        self.img = imread(path)
        self._qimg = QImage(self.img.data, self.img.shape[1], self.img.shape[0], self.img.strides[0], QImage.Format_RGB888)
        print(self.img.__dict__)

        pixm = QPixmap(self._qimg)
        self.lbl.setPixmap(pixm)

        self._ih = pixm.height() // self._y_scale
        self._iw = pixm.width() // self._x_scale

    def change_thresh(self, thresh):
        self.magic_wand(self._x * self._x_scale, self._y * self._y_scale, thresh)

    def magic_wand(self, x, y, thresh=25):

        """Choose a connected component and show the chosen region"""

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

        self._selection = numpy.zeros((self._ih, self._iw, 3), dtype=uint8)
        self._selection[:, :, 0] = numpy.multiply(self.img[:, :, 0], self._mask[1:-1, 1:-1])
        self._selection[:, :, 1] = numpy.multiply(self.img[:, :, 1], self._mask[1:-1, 1:-1])
        self._selection[:, :, 2] = numpy.multiply(self.img[:, :, 2], self._mask[1:-1, 1:-1])

        # contours to represent the type mask
        contours_type, _ = cv2.findContours(self._mask_type[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        draw_type = cv2.drawContours(self.img.copy(), contours_type, -1, (0, 128, 128), 1)

        # contours to represent the current selection
        contours_selection, _ = cv2.findContours(self._mask[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        draw_selection = cv2.drawContours(draw_type.copy(), contours_selection, -1, (128, 128, 0), 1)
        # display both selections
        applied_mask_1 = QImage(draw_selection.data, draw_selection.shape[1], draw_selection.shape[0], draw_selection.strides[0], QImage.Format_RGB888)
        pixm = QPixmap(applied_mask_1)

        self.lbl.setPixmap(pixm.scaled(self.lbl.pixmap().width(),self.lbl.pixmap().height(), Qt.KeepAspectRatio))

    def x2(self):

        # toggle between x2-enlarged and real-size image

        pixm = self.lbl.pixmap()
        y = self.lbl.pixmap().height()
        x = self.lbl.pixmap().width()

        if self._x2_pressed == True:
            self.lbl.setPixmap(pixm.scaled(x // 2, y // 2, Qt.KeepAspectRatio))
            self._x_scale = self._x_scale // 2
            self._y_scale = self._y_scale // 2
            self._x2_pressed = False
        else:
            self.lbl.setPixmap(pixm.scaled(x * 2, y * 2, Qt.KeepAspectRatio))
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
        mask_1 |= (mask_1 == 1) | (mask_2 == 1)
        plt.imshow(mask_1)
        plt.show()

    def subtract_masks(self, mask_1, mask_2):
        mask_1 = (mask_1 == 1) & (mask_2 == 0)

    def create_mask_type(self):

        self._mask_type = numpy.zeros((self._ih+2, self._iw+2), dtype=uint8)

    def get_type(self):
        items = ('river', 'lake', 'road', 'building', 'firebreak', 'cloud', 'cloud shade')
                
        item, ok = QInputDialog.getItem(self, "select input dialog", 
            "surface types", items, 0, False)
                
        if ok and item:
            self.btn_update_mask.setDisabled(False)
            self.btn_save_mask.setDisabled(False)
            self.lbl_type.setText(item)
            self._surface_type = item


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = myGUI()
    sys.exit(app.exec_())
