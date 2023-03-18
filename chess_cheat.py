import numpy as np
import time
import cv2
from mss import mss
from PIL import Image
import pytesseract
import pyautogui

from abc import *

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Corner:
    def __init__(self, topL, topR, botL, botR):
        self.topL = topL
        self.topR = topR
        self.botL = botL
        self.botR = botR

class CornerDetector(ABC):
    
    @abstractmethod
    def detectCorners(self):
        pass


class BoardCornerDetector(CornerDetector):

    def __init__(self):
        self.detected = False
        self.topLeft = None
        self.topRight = None
        self.botLeft = None
        self.botRight = None

    def detectCorners(self):
        if self.detected:
            return self.topLeft, self.topRight, self.botLeft, self.botRight
        self.detected = True
        return self.topLeft, self.topRight, self.botLeft, self.botRight
        
class FullScreenBoardCornerDetector(CornerDetector):

    def __init__(self):
        self.topL = Point(191, 173)
        self.topR = Point(793, 173)
        self.botL = Point(191, 774)
        self.botR = Point(793, 774)

    def detectCorners(self):
        return Corner(self.topL, self.topR, self.botL, self.botR)

        
class NotationCornerDetector(CornerDetector):

    def __init__(self):
        self.topL = Point(860, 223)
        self.topR = Point(1005, 223)
        self.botL = Point(860, 583)
        self.botR = Point(1005, 583)

    def detectCorners(self):
        return Corner(self.topL, self.topR, self.botL, self.botR)


class CornerPropertyReader:

    def __init__(self, corner):
        self.corner = corner

    def getLeft(self):
        print(self.corner.topL.x)
        return self.corner.topL.x
    def getRight(self):
        return self.corner.topR.x
    def getBot(self):
        return self.corner.botL.y
    def getTop(self):
        return self.corner.topL.y
    def getWidth(self):
        return self.getRight() - self.getLeft()
    def getHeight(self):
        return self.getBot() - self.getTop()
    def __str__(self):
        return f"top,left,width,height: {self.getTop()}, {self.getLeft()}, {self.getWidth()}, {self.getHeight()}"
        

class DisplayImage(ABC):
    @abstractmethod
    def displayImage(self, img):
        pass

class DisplayStaticImage(DisplayImage):
    def displayImage(self, img):
        cv2.imshow("img", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

class DisplayVideo:
    def __init__(self, imgReader):
        self.imgReader = imgReader

    def displayVideo(self, corner):
        while True:
            img = self.imgReader.readImage(corner)
            cv2.imshow("img", img)
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                cv2.destroyAllWindows()
                break


class NotationReader(ABC):
    @abstractmethod
    def read(self, corner):
        pass

class RowNotationReader(NotationReader):
    def __init__(self):
        self.imgReader = ImageReader()
        self.notationDetector = NotationCornerDetector()
        self.corner = self.notationDetector.detectCorners()
        self.cornerPropertyReader = CornerPropertyReader(self.corner)
        self.h = self.cornerPropertyReader.getHeight()
        self.w = self.cornerPropertyReader.getWidth()
        self.l = self.cornerPropertyReader.getLeft()
        self.r = self.cornerPropertyReader.getRight()
        self.b = self.cornerPropertyReader.getBot()
        self.t = self.cornerPropertyReader.getTop()

        self.rh = (self.b-self.t) // 12
        self.rw = (self.r-self.l)

    def read(self, rowNumber):
        rowNumber = min(rowNumber-1, 11)
        h = self.rh
        w = self.rw
        tl = Point(self.l, self.t + h * rowNumber)
        bl = Point(self.l, self.t + h * (rowNumber+1))
        br = Point(self.r, self.t + h * (rowNumber+1))
        tr = Point(self.r, self.t + h * rowNumber)
        c = Corner(tl, tr, bl , br)
        img = self.imgReader.readImage(c)
        return img

class WhiteMoveReader:
    def __init__(self):
        self.rowReader = RowNotationReader()
    
    def read(self, rowNum):
        img = self.rowReader.read(rowNum)
        h, w, _ = img.shape
        return img[:,:w//2,:]


class BlackMoveReader:
    def __init__(self):
        self.rowReader = RowNotationReader()
    
    def read(self, rowNum):
        img = self.rowReader.read(rowNum)
        h, w, _ = img.shape
        return img[:,w//2:,:]

class NotationInterpreter:
    def __init__(self):
        self.execpath = "/opt/homebrew/Cellar/tesseract/5.3.0_1/bin/tesseract"
        pytesseract.pytesseract.tesseract_cms = self.execpath
    
    def interpret(self, image):
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return pytesseract.image_to_string(img_rgb)

class ImageReader:
    def __init__(self):
        self.sct = mss()
        

    def readImage(self, corner):
        cornerPropertyReader = CornerPropertyReader(corner)
        bounding_box = {'top': cornerPropertyReader.getTop(), 'left': cornerPropertyReader.getLeft(), 'width': cornerPropertyReader.getWidth(), 'height': cornerPropertyReader.getHeight()}
        return np.array(self.sct.grab(bounding_box))

class ScreenSwitch:
    def switch(self):
        pyautogui.keyDown('command')
        pyautogui.keyDown('tab')
        pyautogui.keyUp('command')
        pyautogui.keyUp('tab')

class Game(ABC):
    @abstractmethod
    def startNewGame(self):
        pass

    @abstractmethod
    def endGame(self):
        pass

class InteractiveGame(Game):
    def __init__(self):
        self.mover = None
        self.inter = NotationInterpreter()

    def startNewGame(self):
        ch = input('white or black? (w/b): ')
        if ch == 'w':
            self.mover = WhiteMoveReader()
        else:
            self.mover = BlackMoveReader()

        whiteTurn = True
        while True:
            if whiteTurn:
                turn = input("Enter White Move: ")
            else:
                turn = input("Enter Black Move: ")
            if turn == "new":
                self.startNewGame()
            whiteTurn = not whiteTurn

#boardDet = FullScreenBoardCornerDetector()
#boardCorner = boardDet.detectCorners()
#notatCorner = NotationCornerDetector().detectCorners()
#notationReader = RowNotationReader()
#whiteMoveReader = WhiteMoveReader()
#blackMoveReader = BlackMoveReader()
##img = notationReader.read(1)
##img = whiteMoveReader.read(1)
#img = blackMoveReader.read(3)
#notationInterpreter = NotationInterpreter()
#print(notationInterpreter.interpret(img))
#displayImage = DisplayStaticImage()
#imageReader = ImageReader()
#displayImage.displayImage(img)
##displayVideo = DisplayVideo(imageReader)
##displayVideo.displayVideo(notatCorner)

screenSwitch = ScreenSwitch()
screenSwitch.switch()
