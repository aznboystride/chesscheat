import numpy as np
import time
import cv2
from mss import mss
from PIL import Image
import pytesseract
import pyautogui
import chess
from skimage.metrics import structural_similarity
from abc import *
import os

class ChessPositionTo2DPointMapper:
    def __init__(self):
        self.cornerDetector = FullScreenBoardCornerDetector()
        self.whiteOrBlack = WhiteOrBlackDetector1()
    def chessPositionTo2D(self, pos):
        chessPosTo2DMap = {}
        is_black = self.whiteOrBlack.isBlack()
        letter_range = range(ord('a'), ord('h') + 1)
        for letter in letter_range:
            for number in range(1, 9):
                chessPosTo2DMap[f"{chr(letter) }{number}"] = Point(letter - ord('a'), 8-number) if not is_black else Point(ord('h') - letter, number-1)
        if pos not in chessPosTo2DMap:
            raise Exception(f"{pos} is not a valid chess position")
        return chessPosTo2DMap[pos]

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return f"{self.x},  {self.y}"

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


class MouseMover(ABC):

    @abstractmethod
    def move(self, pa, pb):
        pass


class MouseDragger(MouseMover):

    def move(self, pa, pb):
        pyautogui.moveTo(pa.x, pa.y)
        time.sleep(1)
        pyautogui.dragTo(pb.x, pb.y, button='left')


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

class WhiteOrBlackDetector(ABC):
    @abstractmethod
    def isBlack(self):
        pass

class PieceImageExtractor:

    def __init__(self):
        self.boardCornerDetector = FullScreenBoardCornerDetector()
        self.whiteOrBlackDetector = WhiteOrBlackDetector1()
        self.posTo2DMapper = ChessPositionTo2DPointMapper()
        self.is_black = self.whiteOrBlackDetector.isBlack()
        self.imageReader = ImageReader()

    def getImage(self, pos):
        corners = self.boardCornerDetector.detectCorners()
        cornerPropertyReader = CornerPropertyReader(corners)
        h = cornerPropertyReader.getHeight()
        w = cornerPropertyReader.getWidth()
        t = cornerPropertyReader.getTop()
        b = cornerPropertyReader.getBot()
        l = cornerPropertyReader.getLeft()
        r = cornerPropertyReader.getRight()
        hr = h // 8
        wr = w // 8
        pos2d = self.posTo2DMapper.chessPositionTo2D(pos)
        col = pos2d.x
        row = pos2d.y
        corner = Corner(
            Point(l+wr*col, t+hr*row),
            Point(l+wr*(col+1), t+hr*row),
            Point(l+wr*col, t+hr*(row+1)),
            Point(l+wr*(col+1), t+hr*(row+1))
        )
        return self.imageReader.readImage(corner)


class WhiteOrBlackDetector1(WhiteOrBlackDetector):

    def __init__(self):
        self.boardCornerDetector = FullScreenBoardCornerDetector()
    def isBlack(self):
        return True

class UciGame(Game):
    def endGame(self):
        pass

    def startNewGame(self):
        pass

    def __init__(self):
        self.board = chess.Board()
        # print(self.board)

class TesseractWrapper:
    def image_to_string(self, image):
        return pytesseract.image_to_string(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


class PieceImageInterpreter(ABC):

    @abstractmethod
    def get_piece(self, image):
        pass


class PieceImageInterpreterEdgeSimilarity(PieceImageInterpreter):
    def __init__(self):
        self.chess_pieces_path = "/Users/fair/Downloads/chesspieces"

    def compare_with_img_path(self, image, image2):
        h, w = image.shape
        image2 = cv2.resize(image2, (w, h))
        image = cv2.Canny(image, 85, 100)
        image2 = cv2.Canny(image2, 85, 100)
        # black = np.zeros((h, w * 2), dtype=np.uint8)
        # black[:h, :w] = image
        # black[:h, w:] = image2
        # cv2.imshow("temp", black)
        # cv2.waitKey(0)
        return structural_similarity(image, image2)

    def get_piece(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        highest = 0
        pick = None
        for root, dirs, files in os.walk(self.chess_pieces_path):
            for f in files:
                pth = os.path.join(root, f)
                image2 = cv2.imread(pth)
                image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
                temp = self.compare_with_img_path(image, image2)
                # print(f"ssim for {f}: {temp}")
                if temp > highest:
                    highest = temp
                    pick = f
        return pick


class PieceImageInterpreterSsimGrayScale(PieceImageInterpreter):
    def __init__(self):
        self.chess_pieces_path = "/Users/fair/Downloads/chesspieces"

    def compare_with_img_path(self, image, image2):
        h, w = image.shape
        image2 = cv2.resize(image2, (w,h))
        black = np.zeros((h, w*2), dtype=np.uint8)
        black[:h,:w] = image
        black[:h,w:] = image2
        cv2.imshow("temp", black)
        cv2.waitKey(0)
        return structural_similarity(image, image2)

    def get_piece(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        highest = 0
        pick = None
        for root, dirs, files in os.walk(self.chess_pieces_path):
            for f in files:
                pth = os.path.join(root, f)
                image2 = cv2.imread(pth)
                image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
                temp = self.compare_with_img_path(image, image2)
                print(f"ssim for {f}: {temp}")
                if temp > highest:
                    highest = temp
                    pick = f
        return pick


class PieceImageInterpreterSsimColored(PieceImageInterpreter):
    def __init__(self):
        self.chess_pieces_path = "/Users/fair/Downloads/chesspieces"

    def compare_with_img_path(self, image, image2):
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        h, w, d = image.shape
        image2 = cv2.resize(image2, (w, h))
        return structural_similarity(image, image2, channel_axis=2)

    def get_piece(self, image):
        highest = 0
        pick = None
        for root, dirs, files in os.walk(self.chess_pieces_path):
            for f in files:
                pth = os.path.join(root, f)
                image2 = cv2.imread(pth)
                temp = self.compare_with_img_path(image, image2)
                print(f"ssim for {f}: {temp}")
                if temp > highest:
                    highest = temp
                    pick = f
        return pick


class PieceMover:
    def __init__(self):
        self.mouseDragger = MouseDragger()
        self.mapper = ChessPositionTo2DPointMapper()

    def move(self, posa, posb):
        pa = self.mapper.chessPositionTo2D(posa)
        pb = self.mapper.chessPositionTo2D(posb)
        self.mouseDragger.move(pa, pb)


# UciGame()
# pieceInterpreter = PieceImageInterpreterEdgeSimilarity()
# displayer = DisplayStaticImage()
# tess = TesseractWrapper()
# pieceExtractor = PieceImageExtractor()
# for c in range(ord('a'), ord('h')+1):
#     for r in range(1, 9):
#         print(chr(c), r)
#         img = pieceExtractor.getImage(f"{chr(c)}{r}")
#         print(pieceInterpreter.get_piece(img))
#         displayer.displayImage(img)

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

pieceMover = PieceMover()
pieceMover.move("h7", "h6")
screenSwitch = ScreenSwitch()
# screenSwitch.switch()
