import os
import sys
import tempfile
from collections import namedtuple
from pathlib import Path
import cv2
import matplotlib.pyplot as plt
import numpy
from imageio import imread, imwrite
from numpy import ones, uint8
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor, QImage, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QButtonGroup, QComboBox,
                             QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                             QInputDialog, QLabel, QPushButton, QRadioButton,
                             QSizeGrip, QSlider, QWidget, QLineEdit)
from windows_and_channels import *
# import mask_tools

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

        # TODO: change plug size to (self._tile_h, self._tile_w) by scaling it
        pixm = QPixmap('plug.jpg').scaled(512, 512)

        # create and initialize image canvas
        self.cnv_img = Canvas(self)
        self.cnv_img.setPixmap(pixm)
        self.cnv_img.pressed.connect(self.magic_wand)

        # create and initialize mask canvas
        self.cnv_msk = Canvas(self)
        self.cnv_msk.setPixmap(pixm)

        # btn_open opens a dialogue for selecting a directory with images to label
        self.btn_choose_bands = QPushButton('Open Bands', self)
        self.btn_choose_bands.pressed.connect(self.choose_bands_dir)
        
        # btn_new_mask ...
        self.btn_choose_masks = QPushButton('Open Masks', self)
        self.btn_choose_masks.pressed.connect(self.choose_masks_dir)
        # self.btn_choose_masks.pressed.connect(self.get_type)
        # self.btn_choose_masks.pressed.connect(self.create_mask_type)
        self.btn_choose_masks.setDisabled(True)

        # btn_add ...
        self.btn_add = QPushButton('Add Selection', self)
        self.btn_add.pressed.connect(self.combine_masks)
        self.btn_add.setDisabled(True)

        # btn_subtract ...
        self.btn_subtract = QPushButton('Subtract Selection', self)
        self.btn_subtract.pressed.connect(self.subtract_masks)      
        self.btn_subtract.setDisabled(True)

        # btn_save_mask ...
        self.bnt_create_mask = QPushButton('Create Mask', self)
        self.bnt_create_mask.pressed.connect(self.create_mask_dialogue)
        self.bnt_create_mask.setDisabled(True)

        # btn_next opens the next image from the directory        
        self.btn_next = QPushButton('Next', self)
        self.btn_next.pressed.connect(self.open_next_tile)
        self.btn_next.setDisabled(True)

        # btn_prev ...
        self.btn_prev = QPushButton('Previuos', self)
        self.btn_prev.pressed.connect(self.open_previous_tile)
        self.btn_prev.setDisabled(True)

        # lbl_info ...
        # TODO: design info-label, set initial text
        self.lbl_info = QLabel(self)
        
        # sld_thresh controls magick wnad treshold
        self.sld_thresh = QSlider(Qt.Horizontal, self)
        self.sld_thresh.setFixedSize(1020, 25)
        self.sld_thresh.setMaximum(255)
        self.sld_thresh.setMinimum(0)
        self.sld_thresh.setSingleStep(1)
        self.sld_thresh.setTickPosition(QSlider.TicksBelow)
        self.sld_thresh.setTickInterval(10)
        self.sld_thresh.valueChanged.connect(self.change_thresh)
        self.sld_thresh.setDisabled(True)
        
        # sld controls the FloodFill threshold value
        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems(['RGB: 1, 2, 3', 'Land/Water: 8, 11, 4', 'NBR'])
        self.cmb_mode.currentIndexChanged.connect(self.set_mode)
        self.cmb_mode.setDisabled(True)

        # sld controls the FloodFill threshold value
        self.cmb_mask = QComboBox(self)
        self.cmb_mask.setEditable(True)
        self.cmb_mask.InsertAtBottom
        self.cmb_mask.setDisabled(True)
        self.cmb_mask.activated.connect(self.choose_mask_file)

        # TODO: remove
        # self.btn_scale = QPushButton('Scale: x2', self)
        # self.btn_scale.pressed.connect(self.x2)
        # self.btn_scale.setDisabled(True)
        
        # set window layout 
        grid = QGridLayout()
        grid.addWidget(self.cnv_img, 0, 0, 7, 1, Qt.AlignCenter)
        grid.addWidget(self.sld_thresh, 7, 0, 1, 2, Qt.AlignCenter)
        grid.addWidget(self.cnv_msk, 0, 1, 7, 1, Qt.AlignCenter)
        grid.addWidget(self.btn_choose_bands, 0, 2, 1, 2, Qt.AlignVCenter)
        grid.addWidget(self.btn_choose_masks, 1, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.lbl_info, 2, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.cmb_mode, 3, 2, 1, 2)
        grid.addWidget(self.cmb_mask, 4, 2, 1, 2)
        grid.addWidget(self.btn_add, 5, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.btn_subtract, 6, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.bnt_create_mask, 7, 2, 1, 2,Qt.AlignVCenter)
        grid.addWidget(self.btn_prev, 8, 2, Qt.AlignVCenter)
        grid.addWidget(self.btn_next, 8, 3, Qt.AlignVCenter)        
        self.setLayout(grid)

        # show the window
        self.show()

    def set_mode(self, e):
        if e == 0:
            # RGB
            self._mode = (1, 2, 3)
        elif e == 1:
            # Land/Water
            self._mode = (7, 11, 3)
        elif e == 2:
            # NBR
            self._mode = (7, 12)
        self.open_map_tile()
        self.draw_contours()

    
    def choose_bands_dir(self):

        """ Select directory with band images """

        self.bands_path = QFileDialog.getExistingDirectoryUrl(self).path()

        if self.bands_path:
            self.state_init()
            self.open_map_tile()

            self.btn_choose_masks.setDisabled(False)

    def choose_masks_dir(self):
        
        """ Select directory with mask files """

        self.masks_path = QFileDialog.getExistingDirectoryUrl(self).path()
        
        if self.masks_path:
            self.cmb_mask.setDisabled(False)
            masks = os.listdir(self.masks_path)
            self.cmb_mask.clear()
            self.cmb_mask.addItems(masks)

            coef_h, coef_w, mh, mw = get_size_coefs(self.bands_path) #wac        
            self._max_band_width = mh
            self._max_band_height = mw
            self._map_size = (mh, mw)

        self.bnt_create_mask.setDisabled(False)

    def choose_mask_file(self, e):

        filename = self.cmb_mask.currentText()
        self._mask_file = np.load(Path(self.masks_path, filename), mmap_mode='r+')
        self.state_active()
        self.open_mask_tile()
        self.state_new_image()

    def combine_masks(self):
        self._mask |= (self._selection == 1)
        self._mask_file[self._y_pos*self.STEP : self._y_pos*self.STEP + self.STEP, self._x_pos*self.STEP : self._x_pos*self.STEP + self.STEP] = self._mask[1:-1, 1:-1]
        self.open_mask_tile()

    def subtract_masks(self):

        self._mask &= (self._selection != 1)
        self._mask_file[self._y_pos*self.STEP : self._y_pos*self.STEP + self.STEP, self._x_pos*self.STEP : self._x_pos*self.STEP + self.STEP] = self._mask[1:-1, 1:-1]
        self.open_mask_tile()

    def open_mask_tile(self):

            self._mask = numpy.zeros(self._mask_size, dtype=uint8)
            self._mask[1:-1, 1:-1] = self._mask_file[self._y_pos*self.STEP : self._y_pos*self.STEP + self.STEP, self._x_pos*self.STEP : self._x_pos*self.STEP + self.STEP]     
            
            qimg = QImage(self._mask * 255, self._mask.shape[1], self._mask.shape[0], self._mask.strides[0], QImage.Format_Grayscale8)        
            pixm_mask = QPixmap(qimg)
            self.cnv_msk.setPixmap(pixm_mask)

    def open_map_tile(self):

        """ Open the next tif file from the chosen directory.
            The .tif file is opened - saved as jpg (by ) - and reopened as jpg.
        """
        # TODO: info-text
        # self.lbl_info.setText('\n'.join([': '.join(i) for i in self.tile_info.items()]))
        # print('!', self._size, list(i * self.STEP for i in self._pos))

        tile_layers = open_chosen_bands(self.bands_path, self._mode, self._tile_size, (self._x_pos * self.STEP, self._y_pos*self.STEP)) #wac
        
        
        if len(tile_layers) == 3:
            # same 
            self.img = equlalize_hist(np.dstack([tile_layers[i] for i in (2, 1, 0)]))  #wac
            self._qimg = QImage(self.img.data, self.img.shape[1], self.img.shape[0], self.img.strides[0], QImage.Format_RGB888) #wac
        if len(tile_layers) == 2:
            # same
            self.img = equlalize_hist(NBR(tile_layers)) #wac           
            self._qimg = QImage(self.img.data, self.img.shape[1], self.img.shape[0], self.img.strides[0], QImage.Format_Indexed8)
        pixm = QPixmap(self._qimg)
        self.cnv_img.setPixmap(pixm.scaled(self.img.shape[1] * self._x_scale, self.img.shape[0]*self._y_scale)) #, Qt.KeepAspectRatio))

    def open_previous_tile(self):        
        if self._x_pos >= 1:
            self._x_pos -= 1

        self._selection = numpy.zeros(self._mask_size, dtype=uint8)

        self.open_mask_tile()

        self.open_map_tile()

    def open_next_tile(self):

        if self._x_pos <= self._max_band_width // self.STEP:
            self._x_pos += 1
        elif self._y_pos <= self._max_band_height // self.STEP:
            self._x_pos = 0
            self._y_pos += 1      

        self._selection = numpy.zeros(self._mask_size, dtype=uint8)

        self.open_mask_tile()

        self.open_map_tile()

    def change_thresh(self, thresh):
        self.magic_wand(self._x_curs* self._x_scale, self._y_curs* self._y_scale, thresh)

    def magic_wand(self, x, y, thresh=25):

        """Choose a connected component and show the chosen region"""

        # enable the magic wand tool only if a surface type for the mask is selected
        if self._wand_enabled == False:
            return None

        # move slider to the initial position
        self.sld_thresh.setValue(thresh)
        # change seedPoint coordinates
        self._x_curs = x // self._x_scale
        self._y_curs = y // self._y_scale      
        seedPoint = Point(self._x_curs, self._y_curs)
        # number of neighbour pixels considered | value to fill the mask
        flags = 4 | (1 << 8)
        # compare considered points to the seed | do not change the pic itself
        flags |= cv2.FLOODFILL_FIXED_RANGE |  cv2.FLOODFILL_MASK_ONLY
        self._selection = numpy.zeros(self._mask_size, dtype=uint8)

        if len(self._mode) == 3:
            # changes the mask inplace
            cv2.floodFill(self.img, self._selection, seedPoint, 0, (thresh,)*3, (thresh,)*3, flags)
        else:
            # changes the mask inplace
            cv2.floodFill(self.img, self._selection, seedPoint, 0, thresh, thresh, flags)

        self.draw_contours()
        
    def draw_contours(self):

        # contours to represent the type mask
        contours_type, _ = cv2.findContours(self._mask[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if len(self._mode) == 3:
            draw_type = cv2.drawContours(self.img.copy(), contours_type, -1, (255, 255, 255), 1)
            # contours to represent the current selection
            contours_selection, _ = cv2.findContours(self._selection[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            draw_selection = cv2.drawContours(draw_type.copy(), contours_selection, -1, (255, 255, 0), 1)
            # display both selections
            applied_mask_1 = QImage(draw_selection.data, draw_selection.shape[1], draw_selection.shape[0], draw_selection.strides[0], QImage.Format_RGB888)
        else:
            draw_type = cv2.drawContours(self.img.copy(), contours_type, -1, 255, 1)
            # contours to represent the current selection
            contours_selection, _ = cv2.findContours(self._selection[1:-1, 1:-1], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            draw_selection = cv2.drawContours(draw_type.copy(), contours_selection, -1, 224, 1)
            # display both selections
            applied_mask_1 = QImage(draw_selection.data, draw_selection.shape[1], draw_selection.shape[0], draw_selection.strides[0], QImage.Format_Indexed8)
        pixm = QPixmap(applied_mask_1)
        self.cnv_img.setPixmap(pixm.scaled(self.cnv_img.pixmap().width(),self.cnv_img.pixmap().height(), Qt.KeepAspectRatio))

    def create_mask(self, name):

        if not name in os.listdir(self.masks_path):

            map_ext = [(self._max_band_height // self._tile_h + 1) *  self._tile_h, (self._max_band_width // self._tile_w + 1) * self._tile_w]
            print(map_ext)
            mask = np.zeros(map_ext, dtype=np.uint8)
            np.save(Path(self.masks_path, name), mask)

    def create_mask_dialogue(self):

        name, _ = QInputDialog.getText(self, "New Mask","Enter new mask name (w/o any extensions):", QLineEdit.Normal, "")

        print(name)

        if name:
            self.create_mask(name)
            items = os.listdir(self.masks_path)
            items.sort()
            self.cmb_mask.addItems(items)


    # def x2(self):

    #     # toggle between x2-enlarged and real-size image

    #     pixm = self.cnv_img.pixmap()
    #     y = self.cnv_img.pixmap().height()
    #     x = self.cnv_img.pixmap().width()

    #     if self._x2_pressed == True:
    #         self.cnv_img.setPixmap(pixm.scaled(x // 2, y // 2, Qt.KeepAspectRatio))
    #         self._x_scale = self._x_scale // 2
    #         self._y_scale = self._y_scale // 2
    #         self._x2_pressed = False
    #     else:
    #         self.cnv_img.setPixmap(pixm.scaled(x * 2, y * 2, Qt.KeepAspectRatio))
    #         self._x_scale = self._x_scale * 2
    #         self._y_scale = self._y_scale * 2
    #         self._x2_pressed = True




    # def create_mask_type(self):     

    #     self._mask = numpy.zeros(self._mask_size, dtype=uint8)
    #     self._mask[1:-1, 1:-1] = mask_tools.open_mask_tile(self._mask_file, (self._y_pos, self._x_pos), (self._tile_h, self._tile_w))
    #     pixm_mask = QPixmap(self._mask[1:-1, 1:-1])
    #     self.cnv_msk.setPixmap(pixm_mask.scaled(self.cnv_img.pixmap().width(),self.cnv_img.pixmap().height(), Qt.KeepAspectRatio))

    # def get_type(self):
        
    #     items = ('river', 'lake', 'road', 'building', 'firebreak', 'cloud', 'cloud shadow')
                
    #     item, ok = QInputDialog.getItem(self, "select input dialog", 
    #         "surface types", items, 0, False)
                
    #     if ok and item:            
    #         self.state_mask(item)
    #         # TODO: change paths
    #         # TODO: change name assignment
    #         dir_path = './masks'
    #         file_name = self._surface_type + '.npy'
    #         masks = mask_tools.check_masks(dir_path)
    #         if file_name not in masks:
    #             mask_tools.create_mask(file_name, dir_path, (self._max_band_height, self._max_band_width))
    #         self._mask_file = mask_tools.open_mask(Path(dir_path, file_name))

    def state_init(self):

        # tile window roll step
        self.STEP = 512

        # tile window position within the whole image
        self._x_pos = 0
        self._y_pos = 0
        self._pos = (self._y_pos, self._x_pos)

        # cursor position within a tile
        self._x_curs= 0
        self._y_curs= 0
        self._curs = (self._y_curs, self._x_curs)

        # default tile size as for the biggest band
        # divided proportionally for smaller bands
        self._tile_h = self.STEP
        self._tile_w = self.STEP
        self._tile_size = (self._tile_h, self._tile_w)

        # default mask tile size
        self._mask_h = self._tile_h + 2  
        self._mask_w = self._tile_w + 2
        self._mask_size = (self._mask_h, self._mask_w)

        # image scale (currently not used)
        # TODO: remove 
        self._x_scale = 1
        self._y_scale = 1

        # bands composition mode
        self._mode = (1, 2, 3)



    def state_active(self):

        "The interface is ready to work with masks"

        

        self._wand_enabled = True
        # TODO: do I need it heree, the mask
        self._selection = numpy.zeros(self._mask_size, dtype=uint8)

        self.btn_add.setDisabled(False)
        self.btn_subtract.setDisabled(False)        
        self.btn_next.setDisabled(False)
        self.btn_prev.setDisabled(False)
        self.cmb_mode.setDisabled(False)
        self.sld_thresh.setDisabled(False)

    
    def state_mask(self, item):

        self.btn_add.setDisabled(False)
        self.btn_subtract.setDisabled(False)
        self.bnt_create_mask.setDisabled(False)
        self.tile_info['layer'] = item
        self.lbl_info.setText('\n'.join([': '.join(i) for i in self.tile_info.items()]))
        self._surface_type = item
        self._wand_enabled = True

    def state_new_image(self):

        self._selection = numpy.zeros(self._mask_size, dtype=uint8)

        # self.open_mask_tile()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = myGUI()
    sys.exit(app.exec_())
