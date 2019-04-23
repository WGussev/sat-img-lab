from imageio import imread, imwrite
import matplotlib.pyplot as plt
from os import mkdir 
from os.path import isdir
from pathlib import Path

# TODO: check the metadata saved
# TODO: 
# NB: here on segmentation http://scipy-lectures.org/advanced/image_processing/

class imgCutter:

    def __init__(self, path):
        self.path = Path(path)
        self.img = imread(self.path)

    def cut_image(self, width=150, height=150):
        # The resulting tile list only references the initial image.
        # Both are stored as object attributes.
        self.rows = self.img.shape[0] // height + 1
        self.cols = self.img.shape[1] // width + 1
        self.tiles = [[0 for i in range(self.cols)] for j in range(self.rows)]
        for i in range(self.rows):
            for j in range(self.cols):
                # All arrays generated by basic slicing are always views of the original array.
                self.tiles[i][j] = self.img[i * height:(i+1)*height, j*width:(j+1)*width, :]
                #self.tiles[i][j] = [slice(i * height, (i+1)*height), slice(j*width, (j+1)*width)]

    def show_image(self):
        plt.imshow(self.img)
        plt.show()

    def show_tiles(self):
        # BUG: crashes, when the tile size is smaller than approx. 150x150
        fig = plt.figure(figsize=(self.rows, self.cols))
        for i in range(self.rows):
            for j in range(self.cols):
                num = i * self.cols + j + 1
                img = self.tiles[i][j]
                #img = self.img[self.tiles[i][j][0], self.tiles[i][j][1], :]
                fig.add_subplot(self.rows, self.cols, num)
                plt.imshow(img)
        plt.show()
    
    def save_tiles(self, dir_path):
        # Saves to the specified directory, even if it's not empty.
        if not isdir(dir_path):
            mkdir(dir_path)
        for i in range(self.rows):
            for j in range(self.cols):
                imwrite(Path(dir_path,str(i)+str(j)+self.path.suffix), self.tiles[i][j], format='tif')


if __name__ == "__main__":
    im = imgCutter('/home/lodya/Desktop/satellite/T43WEP_20170713T065011_TCI.jp2')
    im.cut_image(256, 256)
    im.save_tiles('/home/lodya/Desktop/DigDes/sat-img-lab/tiles_sat')
