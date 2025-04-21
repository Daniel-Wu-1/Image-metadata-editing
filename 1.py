import sys
import os
import random
import json
import datetime
import PyQt5
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, 
                            QFileDialog, QGroupBox, QScrollArea, QCheckBox, QMessageBox,
                            QFrame, QRadioButton, QButtonGroup, QTextEdit, QSplitter,
                            QStackedWidget, QToolTip, QMenu, QAction, QListWidget, 
                            QAbstractItemView, QListWidgetItem, QProgressDialog)
from PyQt5.QtCore import Qt, QSettings, QCoreApplication, QTranslator, QSize, QBuffer, QByteArray, QIODevice, QMimeData, QUrl, QEvent, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QImage, QCursor, QDragEnterEvent, QDropEvent
import exiftool

# 自定义的QComboBox子类，忽略未展开状态下的鼠标滚轮事件
class CustomComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def wheelEvent(self, event):
        # 只有在下拉列表展开时才处理鼠标滚轮事件
        if not self.view().isVisible():
            event.ignore()
        else:
            super().wheelEvent(event)

# 导入PIL/Pillow库用于增强图片支持
try:
    from PIL import Image, ImageQt
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: 未安装Pillow库，某些图片格式可能无法正常显示。建议安装: pip install Pillow")

# 确保找到PyQt5平台插件
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname, 'Qt5', 'plugins', 'platforms')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

# 设置Python的默认编码为UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 自定义文件项类，支持复选框
class FileListItem(QWidget):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)  # 默认选中
        
        self.label = QLabel(self.file_name)
        self.label.setToolTip(file_path)
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label, 1)  # 标签占据剩余空间

class ImageMetadataEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        # 应用程序版本
        self.app_version = "1.0.0"
         
        # 定义特殊选项列表（方便统一管理）
        self.special_options = ["【随机生成】", "【不修改】", "【空数据】", "【自定义...】"]
         
        # 设置窗口标题和大小
        self.setWindowTitle(f"图片元数据编辑器 v{self.app_version}")
        self.setMinimumSize(1200, 800)
        
        # 存储已添加的文件路径
        self.file_paths = []
        self.current_file_path = ""
        self.current_metadata = None
        
        # 初始化设置对象
        self.settings = QSettings("ImageMetadataEditor", "settings")
        
        # 设置ExifTool路径
        self.exiftool_path = ""  # 初始化为空
        
        # 初始化元数据选项
        self._init_metadata_options()
        
        # 初始化界面组件
        self.init_ui()
        
        # 检查ExifTool路径并更新UI
        self.check_exiftool_path()
        
        # 使用绝对路径设置图标
        try:
            # 尝试绝对路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(script_dir, "001.ico")
            
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            elif os.path.exists("001.ico"):
                self.setWindowIcon(QIcon("001.ico"))
        except Exception as e:
            print(f"设置窗口图标出错: {e}")
        
        # 加载首选项
        self.load_settings()
        
        # 初始化文件列表
        self.files = []
        self.current_index = -1
        
        # 设置应用程序样式，确保对话框能够更好地显示
        QApplication.setStyle("Fusion")
        
        # 初始化ExifTool进程
        self.exiftool_process = None
        self.start_exiftool()
        
        # 设置事件过滤器，用于处理自定义悬停提示
        self.image_preview.installEventFilter(self)
        
        # 加载上次会话的设置
        self.load_last_session_settings()
    
    # 添加一个简单的start_exiftool方法
    def start_exiftool(self):
        """初始化ExifTool进程"""
        try:
            if self.exiftool_path and os.path.exists(self.exiftool_path):
                # 如果exiftool.exe存在，则打开一个持久化进程
                self.exiftool_process = exiftool.ExifToolHelper(executable=self.exiftool_path)
                print(f"ExifTool已初始化: {self.exiftool_path}")
            else:
                # 使用默认路径或者自动搜索
                try:
                    self.exiftool_process = exiftool.ExifToolHelper()
                    print("ExifTool已使用默认路径初始化")
                except Exception as e:
                    print(f"无法初始化ExifTool: {str(e)}")
                    # 不要中断应用程序，让UI仍然可以显示
                    pass
        except Exception as e:
            print(f"ExifTool初始化错误: {str(e)}")
            # 报错但不中断应用程序运行
    
    def _init_metadata_options(self):
        """初始化所有元数据选项"""
        # Camera makes and models
        self.metadata_options = {
            "make": ["Apple", "Samsung", "Huawei", "Xiaomi", "Google", "OnePlus", "OPPO", "Vivo", "Sony", "LG", 
                     "Nokia", "Motorola", "Honor", "Realme", "ZTE", "Asus", "Lenovo", "Meizu", "Canon", "Nikon", 
                     "Panasonic", "Fujifilm", "Olympus", "Pentax", "Leica", "GoPro", "DJI"],
            "model": {
                "Apple": ["iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus", "iPhone 15", 
                          "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14 Plus", "iPhone 14",
                          "iPhone 13 Pro Max", "iPhone 13 Pro", "iPhone 13", "iPhone 13 Mini",
                          "iPhone 12 Pro Max", "iPhone 12 Pro", "iPhone 12", "iPhone 12 Mini",
                          "iPhone 11 Pro Max", "iPhone 11 Pro", "iPhone 11", "iPhone XS Max", 
                          "iPhone XS", "iPhone XR", "iPhone X", "iPhone SE (3rd gen)", 
                          "iPhone SE (2nd gen)", "iPad Pro 12.9-inch (6th gen)", "iPad Pro 11-inch (4th gen)"],
                "Samsung": ["Galaxy S23 Ultra", "Galaxy S23+", "Galaxy S23", "Galaxy S22 Ultra", 
                            "Galaxy S22+", "Galaxy S22", "Galaxy S21 FE", "Galaxy S21 Ultra", 
                            "Galaxy S21+", "Galaxy S21", "Galaxy Z Fold5", "Galaxy Z Fold4", 
                            "Galaxy Z Fold3", "Galaxy Z Flip5", "Galaxy Z Flip4", "Galaxy Z Flip3",
                            "Galaxy Note 20 Ultra", "Galaxy Note 20", "Galaxy A54", "Galaxy A53",
                            "Galaxy A34", "Galaxy A33", "Galaxy M34", "Galaxy F54"],
                "Huawei": ["P60 Pro", "P60", "P50 Pro", "P50", "P40 Pro+", "P40 Pro", "P40", 
                           "Mate 50 Pro", "Mate 50", "Mate 40 Pro+", "Mate 40 Pro", "Mate 40", 
                           "Mate 30 Pro", "Mate 30", "Mate X3", "Mate X2", "Mate Xs2", "Mate Xs",
                           "Nova 12 Pro", "Nova 12", "Nova 11 Pro", "Nova 11", "Nova 10 Pro", "Nova 10"],
                "Xiaomi": ["Xiaomi 13 Ultra", "Xiaomi 13 Pro", "Xiaomi 13", "Xiaomi 13 Lite", 
                           "Xiaomi 12 Ultra", "Xiaomi 12 Pro", "Xiaomi 12", "Xiaomi 12 Lite", 
                           "Xiaomi 12S Ultra", "Xiaomi 12S Pro", "Xiaomi 12S", "Xiaomi 11 Ultra", 
                           "Xiaomi 11 Pro", "Xiaomi 11", "Redmi Note 12 Pro+", "Redmi Note 12 Pro", 
                           "Redmi Note 12", "Redmi Note 11 Pro+", "Redmi Note 11 Pro", "Redmi Note 11",
                           "POCO F5 Pro", "POCO F5", "POCO F4 GT", "POCO F4", "POCO X5 Pro", "POCO X5"],
                "Google": ["Pixel 7 Pro", "Pixel 7", "Pixel 7a", "Pixel 6 Pro", "Pixel 6", "Pixel 6a",
                           "Pixel 5", "Pixel 5a", "Pixel 4 XL", "Pixel 4", "Pixel 4a", "Pixel 3 XL", 
                           "Pixel 3", "Pixel 3a XL", "Pixel 3a", "Pixel Fold"],
                "OnePlus": ["OnePlus 11", "OnePlus 10 Pro", "OnePlus 10T", "OnePlus 10R", "OnePlus 9 Pro", 
                            "OnePlus 9", "OnePlus 9R", "OnePlus 9RT", "OnePlus 8 Pro", "OnePlus 8", "OnePlus 8T", 
                            "OnePlus Nord 3", "OnePlus Nord 2T", "OnePlus Nord 2", "OnePlus Nord CE 3", "OnePlus Nord CE 2"],
                "OPPO": ["Find X6 Pro", "Find X6", "Find X5 Pro", "Find X5", "Find X5 Lite", "Find X3 Pro",
                         "Find X3", "Find X3 Lite", "Find X3 Neo", "Find N2 Flip", "Find N2", "Find N",
                         "Reno10 Pro+", "Reno10 Pro", "Reno10", "Reno9 Pro+", "Reno9 Pro", "Reno9",
                         "Reno8 Pro+", "Reno8 Pro", "Reno8", "F23", "F21 Pro", "F19 Pro+"],
                "Vivo": ["X90 Pro+", "X90 Pro", "X90", "X80 Pro", "X80", "X70 Pro+", "X70 Pro", "X70",
                         "X60 Pro+", "X60 Pro", "X60", "V29 Pro", "V29", "V27 Pro", "V27", "V25 Pro", "V25",
                         "V23 Pro", "V23", "Y100", "Y77", "Y73", "Y55"],
                "Sony": ["Xperia 1 V", "Xperia 1 IV", "Xperia 1 III", "Xperia 1 II", "Xperia 1",
                         "Xperia 5 IV", "Xperia 5 III", "Xperia 5 II", "Xperia 5", "Xperia 10 V", 
                         "Xperia 10 IV", "Xperia 10 III", "Xperia 10 II", "Xperia 10", "Xperia Pro-I", "Xperia Pro"],
                "LG": ["V60 ThinQ", "V50 ThinQ", "V40 ThinQ", "G8 ThinQ", "G7 ThinQ", "Velvet", "Wing", "K92", "K52", "K42", "Stylo 6"],
                "Nokia": ["X30", "X20", "X10", "G60", "G50", "G21", "G20", "G10", "C32", "C22", "C21", "C12", "C02"],
                "Motorola": ["Edge 40 Pro", "Edge 40", "Edge 30 Ultra", "Edge 30 Pro", "Edge 30", "Edge 20 Pro", 
                             "Edge 20", "Razr 40 Ultra", "Razr 40", "Moto G84", "Moto G73", "Moto G72", "Moto G53", "Moto G52"],
                "Honor": ["Magic5 Pro", "Magic5", "Magic4 Pro", "Magic4", "Magic V2", "Magic Vs", "Magic V",
                          "Honor 90 Pro", "Honor 90", "Honor 80 Pro", "Honor 80", "Honor 70 Pro+", "Honor 70 Pro", "Honor 70"],
                "Realme": ["GT 5 Pro", "GT 5", "GT 3 Pro", "GT 3", "GT Neo5", "GT Neo3", "GT Neo2", "GT Neo",
                           "11 Pro+", "11 Pro", "11", "10 Pro+", "10 Pro", "10", "9 Pro+", "9 Pro", "9"],
                "ZTE": ["Axon 40 Ultra", "Axon 30 Ultra", "Axon 20", "Blade A73", "Blade A72", "Blade A52"],
                "Asus": ["Zenfone 10", "Zenfone 9", "Zenfone 8", "ROG Phone 7 Ultimate", "ROG Phone 7", "ROG Phone 6"],
                "Lenovo": ["Legion Phone Duel 2", "Legion Phone Duel", "K14 Plus", "K14", "K13", "K12 Pro"],
                "Meizu": ["20 Pro", "20", "18 Pro", "18", "17 Pro", "17", "16s Pro", "16s"],
                "Canon": ["EOS R5", "EOS R6 Mark II", "EOS R6", "EOS R7", "EOS R10", "EOS R50", 
                          "EOS 5D Mark IV", "EOS 6D Mark II", "EOS 90D", "EOS 850D", "PowerShot G7 X Mark III"],
                "Nikon": ["Z9", "Z8", "Z7 II", "Z6 II", "Z5", "Z50", "Z30", "D850", "D780", "D7500", "D5600", "D3500", "COOLPIX P1000"],
                "Panasonic": ["Lumix DC-S5 II", "Lumix DC-S5", "Lumix DC-S1R", "Lumix DC-S1", "Lumix DC-G9", "Lumix DC-GH6", "Lumix DC-GH5 II"],
                "Fujifilm": ["X-T5", "X-T4", "X-T3", "X-H2S", "X-H2", "X-H1", "X-Pro3", "X-Pro2", "X-E4", "X-S20", "X-S10", "GFX 100S", "GFX 50S II"],
                "Olympus": ["OM-1", "OM-5", "OM-D E-M1 Mark III", "OM-D E-M5 Mark III", "OM-D E-M10 Mark IV", "PEN E-P7", "Tough TG-6"],
                "Pentax": ["K-3 Mark III", "K-1 Mark II", "K-70", "KP", "645Z"],
                "Leica": ["M11", "M10-R", "M10-P", "M10", "Q3", "Q2", "SL2-S", "SL2", "CL", "TL2", "D-Lux 7"],
                "GoPro": ["HERO11 Black", "HERO10 Black", "HERO9 Black", "HERO8 Black", "MAX"],
                "DJI": ["Mavic 3 Pro", "Mavic 3", "Air 3", "Air 2S", "Mini 3 Pro", "Mini 3", "Mini 2", "Osmo Action 3", "Osmo Action 2"]
            },
            "software": ["iOS 17.2", "iOS 17.1", "iOS 17.0", "iOS 16.7", "iOS 16.6", "iOS 16.5", "iOS 16.4", "iOS 16.3", "iOS 16.2", "iOS 16.1", "iOS 16.0", 
                         "iOS 15.7", "iOS 15.6", "iOS 15.5", "iOS 15.4", "iOS 15.3", "iOS 15.2", "iOS 15.1", "iOS 15.0",
                         "Android 14", "Android 13", "Android 12L", "Android 12", "Android 11", "Android 10",
                         "HarmonyOS 4.0", "HarmonyOS 3.1", "HarmonyOS 3.0", "HarmonyOS 2.0",
                         "One UI 6.0", "One UI 5.1", "One UI 5.0", "One UI 4.1", "One UI 4.0", "One UI 3.1",
                         "MIUI 14", "MIUI 13", "MIUI 12.5", "MIUI 12", "MIUI 11",
                         "ColorOS 14", "ColorOS 13", "ColorOS 12", "ColorOS 11",
                         "OxygenOS 14", "OxygenOS 13", "OxygenOS 12", "OxygenOS 11",
                         "Funtouch OS 14", "Funtouch OS 13", "Funtouch OS 12", "Funtouch OS 11",
                         "Realme UI 5.0", "Realme UI 4.0", "Realme UI 3.0", "Realme UI 2.0",
                         "MagicOS 8.0", "MagicOS 7.0", "MagicOS 6.0",
                         "Origin OS 3", "Origin OS 2", "Origin OS",
                         "Flyme 10", "Flyme 9", "Flyme 8",
                         "Adobe Photoshop 2024", "Adobe Photoshop 2023", "Adobe Photoshop 2022", "Adobe Photoshop 2021",
                         "Adobe Lightroom Classic 12.5", "Adobe Lightroom Classic 12.0", "Adobe Lightroom Classic 11.0",
                         "Adobe Lightroom 7.5", "Adobe Lightroom 7.0", "Adobe Lightroom 6.0",
                         "Capture One 23", "Capture One 22", "Capture One 21",
                         "DxO PhotoLab 7", "DxO PhotoLab 6", "DxO PhotoLab 5",
                         "Luminar AI", "Luminar Neo", "Affinity Photo 2", "Affinity Photo",
                         "Canon Digital Photo Professional 4", "Nikon NX Studio", "Sony Imaging Edge"],
            "lens_model": ["Wide camera", "Ultra Wide camera", "Telephoto camera", "Periscope Telephoto camera", 
                          "Front camera", "Dual lens camera", "Main camera", "Selfie camera", "Macro camera", "Portrait camera",
                          "Canon EF 24-70mm f/2.8L II USM", "Canon EF 70-200mm f/2.8L IS III USM", "Canon RF 24-70mm F2.8 L IS USM", 
                          "Canon RF 50mm F1.2 L USM", "Canon RF 70-200mm F2.8 L IS USM", "Canon RF 100-500mm F4.5-7.1 L IS USM",
                          "Nikon AF-S 24-70mm f/2.8E ED VR", "Nikon AF-S 70-200mm f/2.8E FL ED VR", "Nikon Z 24-70mm f/2.8 S", 
                          "Nikon Z 50mm f/1.8 S", "Nikon Z 70-200mm f/2.8 VR S", "Nikon Z 100-400mm f/4.5-5.6 VR S",
                          "Sony FE 24-70mm F2.8 GM II", "Sony FE 70-200mm F2.8 GM OSS II", "Sony FE 16-35mm F2.8 GM", 
                          "Sony FE 50mm F1.2 GM", "Sony FE 100-400mm F4.5-5.6 GM OSS", "Sony FE 200-600mm F5.6-6.3 G OSS",
                          "ZEISS Otus 55mm f/1.4", "ZEISS Otus 85mm f/1.4", "ZEISS Batis 25mm f/2", 
                          "Sigma 35mm F1.4 DG HSM Art", "Sigma 85mm F1.4 DG HSM Art", "Sigma 24-70mm F2.8 DG DN Art",
                          "Tamron 28-75mm F/2.8 Di III VXD G2", "Tamron 70-180mm F/2.8 Di III VXD", "Tamron 17-28mm F/2.8 Di III RXD"],
            "exposure_time": ["1/15", "1/30", "1/60", "1/120", "1/240", "1/480", "1/960", "1/1000"],
            "fnumber": ["1.6", "1.8", "2.0", "2.2", "2.4", "2.8", "4.0"],
            "iso": ["32", "64", "100", "200", "400", "800", "1600", "3200"],
            "focal_length": ["3.5mm", "4.2mm", "5.7mm", "6.0mm", "7.5mm", "9.0mm", "10.8mm"],
            "white_balance": ["Auto", "Manual", "Daylight", "Cloudy", "Tungsten", "Fluorescent"],
            "flash": ["No Flash", "Flash Fired", "Flash Not Fired", "Auto Flash", "Red-eye Reduction"],
            "orientation": ["Horizontal (normal)", "Mirror horizontal", "Rotate 180", "Mirror vertical", 
                            "Mirror horizontal and rotate 270 CW", "Rotate 90 CW", "Mirror horizontal and rotate 90 CW", "Rotate 270 CW"],
            "latitude_ref": ["N", "S"],
            "longitude_ref": ["E", "W"],
            "altitude_ref": ["Above Sea Level", "Below Sea Level"],
            "country": ["United States", "China", "Japan", "Germany", "United Kingdom", "France", "Italy", 
                        "Canada", "Australia", "Spain", "Russia", "Brazil", "India", "South Korea", "Mexico", "Taiwan"]
        }
        
        # 中文元数据选项
        self.metadata_options_cn = {
            "white_balance": ["自动", "手动", "日光", "阴天", "钨丝灯", "荧光灯"],
            "flash": ["无闪光灯", "闪光灯已触发", "闪光灯未触发", "自动闪光灯", "红眼减轻"],
            "orientation": ["水平（正常）", "水平镜像", 
                            "水平镜像并逆时针旋转270度", "顺时针旋转90度", "水平镜像并逆时针旋转90度", "逆时针旋转270度"],
            "latitude_ref": ["北纬", "南纬"],
            "longitude_ref": ["东经", "西经"],
            "altitude_ref": ["海平面以上", "海平面以下"],
            "country": ["美国", "中国", "日本", "德国", "英国", "法国", "意大利", 
                        "加拿大", "澳大利亚", "西班牙", "俄罗斯", "巴西", "印度", "韩国", "墨西哥", "台湾"]
        }
        
        # 英文到中文的映射
        self.en_to_cn_mapping = {
            "white_balance": {
                "Auto": "自动", "Manual": "手动", "Daylight": "日光", 
                "Cloudy": "阴天", "Tungsten": "钨丝灯", "Fluorescent": "荧光灯"
            },
            "flash": {
                "No Flash": "无闪光灯", "Flash Fired": "闪光灯已触发", 
                "Flash Not Fired": "闪光灯未触发", "Auto Flash": "自动闪光灯", 
                "Red-eye Reduction": "红眼减轻"
            },
            "latitude_ref": {"N": "北纬", "S": "南纬"},
            "longitude_ref": {"E": "东经", "W": "西经"},
            "altitude_ref": {"Above Sea Level": "海平面以上", "Below Sea Level": "海平面以下"}
        }
        
        # 中文到英文的映射
        self.cn_to_en_mapping = {
            "white_balance": {
                "自动": "Auto", "手动": "Manual", "日光": "Daylight", 
                "阴天": "Cloudy", "钨丝灯": "Tungsten", "荧光灯": "Fluorescent"
            },
            "flash": {
                "无闪光灯": "No Flash", "闪光灯已触发": "Flash Fired", 
                "闪光灯未触发": "Flash Not Fired", "自动闪光灯": "Auto Flash", 
                "红眼减轻": "Red-eye Reduction"
            },
            "latitude_ref": {"北纬": "N", "南纬": "S"},
            "longitude_ref": {"东经": "E", "西经": "W"},
            "altitude_ref": {"海平面以上": "Above Sea Level", "海平面以下": "Below Sea Level"}
        }
    
    def check_exiftool_path(self):
        # 首先尝试从已保存的设置中获取路径
        settings = QSettings("ImageMetadataEditor", "settings")
        saved_path = settings.value("exiftool_path", "")
        
        if saved_path and os.path.exists(saved_path):
            self.exiftool_path = saved_path
            self.exiftool_path_edit.setText(self.exiftool_path) if hasattr(self, 'exiftool_path_edit') else None
            print(f"使用保存的ExifTool路径: {self.exiftool_path}")
            return
        
        # 检查默认安装路径
        user_profile = os.environ.get('USERPROFILE', '')
        username = os.path.basename(user_profile) if user_profile else "九筒"  # 默认使用九筒作为用户名
        
        default_paths = [
            "C:\\Program Files\\ExifTool\\exiftool.exe",  # 默认安装位置
            "C:\\Program Files (x86)\\ExifTool\\exiftool.exe",
            f"C:\\Users\\{username}\\Desktop\\exiftool-13.27_64\\exiftool.exe",  # 用户提到的路径
            f"C:\\Users\\{username}\\Desktop\\exiftool-13.27_64\\exiftool(-k).exe",  # 另一种可能的文件名
            f"C:\\Users\\{username}\\Desktop\\exiftool-13.27_64\\exiftool.pl",  # Perl脚本版本
            os.path.join(os.environ.get('USERPROFILE', ''), "Desktop", "exiftool-13.27_64", "exiftool.exe"),
            os.path.join(os.environ.get('USERPROFILE', ''), "Desktop", "exiftool-13.27_64", "exiftool(-k).exe"),
            os.path.join(os.environ.get('USERPROFILE', ''), "Desktop", "exiftool-13.27_64", "exiftool.pl"),
            os.path.join(os.environ.get('USERPROFILE', ''), "Desktop", "exiftool", "exiftool.exe"),
            os.path.join(os.environ.get('USERPROFILE', ''), "Downloads", "exiftool-13.27_64", "exiftool.exe"),
            os.path.join(os.getcwd(), "exiftool.exe"),
            os.path.join(os.getcwd(), "exiftool(-k).exe"),
            os.path.join(os.getcwd(), "exiftool-13.27_64", "exiftool.exe"),
            os.path.join(os.getcwd(), "exiftool-13.27_64", "exiftool(-k).exe"),
            "C:\\Windows\\System32\\exiftool.exe",
        ]
        
        # 打印所有检查的路径以便调试
        print("正在检查以下ExifTool路径:")
        for path in default_paths:
            print(f"  - {path}")
        
        for path in default_paths:
            if os.path.exists(path):
                self.exiftool_path = path
                # 保存找到的路径
                settings.setValue("exiftool_path", self.exiftool_path)
                # 如果UI已经初始化，则更新路径显示
                if hasattr(self, 'exiftool_path_edit'):
                    self.exiftool_path_edit.setText(self.exiftool_path)
                print(f"找到并使用ExifTool路径: {self.exiftool_path}")
                return
        
        # 如果没有找到，尝试搜索可能的目录
        possible_directories = [
            f"C:\\Users\\{username}\\Desktop",
            os.path.join(os.environ.get('USERPROFILE', ''), "Desktop"),
            os.path.join(os.environ.get('USERPROFILE', ''), "Downloads"),
            os.getcwd()
        ]
        
        for directory in possible_directories:
            if os.path.exists(directory):
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if file.lower() in ["exiftool.exe", "exiftool(-k).exe", "exiftool.pl"]:
                            full_path = os.path.join(root, file)
                            self.exiftool_path = full_path
                            settings.setValue("exiftool_path", self.exiftool_path)
                            if hasattr(self, 'exiftool_path_edit'):
                                self.exiftool_path_edit.setText(self.exiftool_path)
                            print(f"在目录搜索中找到ExifTool路径: {self.exiftool_path}")
                            return
        
        # 如果没有找到，提示用户手动指定
        def show_exiftool_dialog():
            msg = QMessageBox()
            msg.setWindowTitle("未找到ExifTool")
            msg.setText("未能找到ExifTool可执行文件。是否指定其位置？\n\n请检查您的ExifTool是否已解压到桌面，路径示例：\nC:\\Users\\九筒\\Desktop\\exiftool-13.27_64\\exiftool.exe")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            
            if msg.exec_() == QMessageBox.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    None, "选择ExifTool可执行文件", "", "可执行文件 (*.exe);;Perl脚本 (*.pl);;所有文件 (*.*)"
                )
                if path and os.path.exists(path):
                    self.exiftool_path = path
                    # 保存用户选择的路径
                    settings.setValue("exiftool_path", self.exiftool_path)
                    # 如果UI已经初始化，则更新路径显示
                    if hasattr(self, 'exiftool_path_edit'):
                        self.exiftool_path_edit.setText(self.exiftool_path)
                    print(f"用户手动选择ExifTool路径: {self.exiftool_path}")
                else:
                    show_exiftool_dialog()  # 如果用户取消，再次显示对话框
            else:
                # 用户选择No，提示将无法使用程序
                QMessageBox.critical(
                    None, "错误", 
                    "ExifTool是本应用程序正常运行所必需的。"
                    "请从https://exiftool.org/下载并重试。"
                )
                sys.exit(1)
        
        # 在主窗口初始化完成后显示对话框
        QCoreApplication.processEvents()
        show_exiftool_dialog()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # ExifTool Path Group
        exiftool_group = QGroupBox("ExifTool设置")
        exiftool_layout = QHBoxLayout()
        
        self.exiftool_path_edit = QLineEdit()
        self.exiftool_path_edit.setReadOnly(True)
        self.exiftool_path_edit.setText(self.exiftool_path if self.exiftool_path else "未设置ExifTool路径")
        
        exiftool_browse_button = QPushButton("设置ExifTool路径...")
        exiftool_browse_button.clicked.connect(self.browse_exiftool)
        
        exiftool_layout.addWidget(self.exiftool_path_edit)
        exiftool_layout.addWidget(exiftool_browse_button)
        exiftool_group.setLayout(exiftool_layout)
        main_layout.addWidget(exiftool_group)
        
        # Create a horizontal splitter to divide image preview and controls
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)  # 防止分割区域被完全收缩
        
        # Left side - Image preview and file list
        left_side = QWidget()
        left_layout = QVBoxLayout(left_side)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image preview label
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        
        preview_label = QLabel("图片预览")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumSize(300, 300)
        self.image_preview.setFrameShape(QFrame.Box)
        self.image_preview.setFrameShadow(QFrame.Sunken)
        self.image_preview.setStyleSheet("background-color: #f0f0f0;")
        self.image_preview.setText("选择图片后显示预览\n支持拖放图片到此处")
        
        # 图片预览区域的信息标签
        self.image_info = QLabel()
        self.image_info.setAlignment(Qt.AlignCenter)
        self.image_info.setWordWrap(True)
        self.image_info.setStyleSheet("color: #555; font-size: 11px;")
        
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.image_preview)
        preview_layout.addWidget(self.image_info)
        
        # File list area
        file_list_widget = QWidget()
        file_list_layout = QVBoxLayout(file_list_widget)
        
        file_list_label = QLabel("选择的图片文件")
        file_list_label.setFont(QFont("Arial", 12, QFont.Bold))
        file_list_layout.addWidget(file_list_label)
        
        # 文件列表和按钮的水平布局
        file_buttons_layout = QHBoxLayout()
        
        # 添加文件按钮
        add_file_button = QPushButton("添加文件")
        add_file_button.clicked.connect(self.browse_file)
        add_file_button.setToolTip("选择一个或多个图片文件")
        
        # 清除文件按钮
        clear_files_button = QPushButton("清除全部")
        clear_files_button.clicked.connect(self.clear_file_list)
        clear_files_button.setToolTip("清除所有选中的文件")
        
        # 添加全选按钮
        select_all_button = QPushButton("全选")
        select_all_button.clicked.connect(self.select_all_files)
        select_all_button.setToolTip("选中所有文件")
        
        # 添加反选按钮
        invert_selection_button = QPushButton("反选")
        invert_selection_button.clicked.connect(self.invert_file_selection)
        invert_selection_button.setToolTip("反转选择状态")
        
        # 添加排序按钮
        sort_button = QPushButton("排序")
        sort_button.setToolTip("对文件列表进行排序")
        sort_button.clicked.connect(self.show_sort_menu)
        
        # 添加批处理提示
        batch_label = QLabel("提示: 支持批量修改多个文件")
        batch_label.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
        
        file_buttons_layout.addWidget(add_file_button)
        file_buttons_layout.addWidget(clear_files_button)
        file_buttons_layout.addWidget(select_all_button)
        file_buttons_layout.addWidget(invert_selection_button)
        file_buttons_layout.addWidget(sort_button)
        
        file_list_layout.addLayout(file_buttons_layout)
        file_list_layout.addWidget(batch_label)
        
        # 文件列表 - 使用QListWidget
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.NoSelection)  # 不使用自带的选择模式
        self.file_list.setDragEnabled(False)
        self.file_list.setAcceptDrops(True)
        self.file_list.setMinimumHeight(100)
        self.file_list.itemClicked.connect(self.on_file_clicked)  # 改为点击事件
        
        file_list_layout.addWidget(self.file_list)
        
        # 添加进度信息标签
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #555; font-size: 10px;")
        file_list_layout.addWidget(self.progress_label)
        
        # 垂直分割预览区和文件列表
        preview_file_splitter = QSplitter(Qt.Vertical)
        preview_file_splitter.addWidget(preview_widget)
        preview_file_splitter.addWidget(file_list_widget)
        preview_file_splitter.setSizes([300, 200])
        
        left_layout.addWidget(preview_file_splitter)
        
        # 右侧区域 - 元数据编辑
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 随机生成标签页
        random_tab = QWidget()
        random_layout = QVBoxLayout(random_tab)
        
        random_description = QLabel("点击下方按钮生成随机的但真实的元数据信息。")
        random_description.setWordWrap(True)
        
        random_button = QPushButton("生成随机元数据")
        random_button.setMinimumHeight(40)
        random_button.clicked.connect(self.generate_random_metadata)
        
        random_layout.addWidget(random_description)
        random_layout.addWidget(random_button)
        random_layout.addStretch()
        
        # 自定义标签页
        custom_tab = QWidget()
        
        # 使用滚动区域
        custom_scroll = QScrollArea()
        custom_scroll.setWidgetResizable(True)
        custom_scroll.setWidget(custom_tab)
        
        self.custom_layout = QVBoxLayout(custom_tab)
        
        # 添加默认设置按钮区域
        default_settings_group = QGroupBox("设置模板")
        default_settings_layout = QHBoxLayout()
        
        save_as_default_button = QPushButton("保存当前设置为模板")
        save_as_default_button.clicked.connect(self.save_as_default_settings)
        save_as_default_button.setToolTip("将当前所有设置保存为模板，方便下次使用")
        
        reset_to_default_button = QPushButton("加载设置模板")
        reset_to_default_button.clicked.connect(self.reset_to_default_settings)
        reset_to_default_button.setToolTip("从保存的模板中恢复设置")
        
        reset_all_button = QPushButton("重置所有设置")
        reset_all_button.clicked.connect(self.reset_settings)
        reset_all_button.setToolTip("将所有设置恢复为初始状态")
        
        default_settings_layout.addWidget(save_as_default_button)
        default_settings_layout.addWidget(reset_to_default_button)
        default_settings_layout.addWidget(reset_all_button)
        default_settings_group.setLayout(default_settings_layout)
        
        # 添加到自定义模式布局
        self.custom_layout.addWidget(default_settings_group)
        
        # EXIF Camera Information
        self.add_section_to_custom("相机与设备信息 (EXIF)", [
            ("品牌", "make", "combobox", self.metadata_options["make"]),
            ("型号", "model", "combobox", []),
            ("软件", "software", "combobox", self.metadata_options["software"]),
            ("镜头型号", "lens_model", "combobox", self.metadata_options["lens_model"]),  # 改为下拉框以支持更多选项
            ("曝光时间", "exposure_time", "combobox", self.metadata_options["exposure_time"]),
            ("光圈值", "fnumber", "combobox", self.metadata_options["fnumber"]),
            ("ISO", "iso", "combobox", self.metadata_options["iso"]),
            ("焦距", "focal_length", "combobox", self.metadata_options["focal_length"]),
            ("白平衡", "white_balance", "combobox", self.metadata_options_cn["white_balance"]),
            ("闪光灯", "flash", "combobox", self.metadata_options_cn["flash"]),
            ("方向", "orientation", "combobox", self.metadata_options_cn["orientation"])
        ])
        
        # Date and Time Information
        current_date = datetime.datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        self.add_section_to_custom("日期与时间信息", [
            ("原始拍摄时间", "date_time_original", "text", current_date),
            ("创建日期", "create_date", "text", current_date),
            ("修改日期", "modify_date", "text", current_date)
        ])
        
        # GPS Information
        self.add_section_to_custom("GPS位置信息", [
            ("纬度", "gps_latitude", "text", ""),
            ("纬度参考", "gps_latitude_ref", "combobox", self.metadata_options_cn["latitude_ref"]),
            ("经度", "gps_longitude", "text", ""),
            ("经度参考", "gps_longitude_ref", "combobox", self.metadata_options_cn["longitude_ref"]),
            ("高度", "gps_altitude", "text", ""),
            ("高度参考", "gps_altitude_ref", "combobox", self.metadata_options_cn["altitude_ref"]),
            ("时间戳", "gps_time_stamp", "text", ""),
            ("日期戳", "gps_date_stamp", "text", "")
        ])
        
        # IPTC/XMP Information
        self.add_section_to_custom("IPTC/XMP信息", [
            ("创建者", "creator", "text", ""),
            ("版权信息", "copyright_notice", "text", ""),
            ("描述", "description", "text", ""),
            ("标题", "title", "text", ""),
            ("关键词", "keywords", "text", ""),
            ("位置", "location", "text", "")
        ])
        
        # 应用按钮
        apply_button = QPushButton("应用自定义元数据")
        apply_button.setMinimumHeight(40)
        apply_button.clicked.connect(self.apply_custom_metadata)
        
        self.custom_layout.addWidget(apply_button)
        
        # 重置设置按钮部分已删除
        
        # 添加标签页
        tab_widget.addTab(random_tab, "随机模式")
        tab_widget.addTab(custom_scroll, "自定义模式")
        
        right_layout.addWidget(tab_widget)
        
        # 添加左右部件到分隔器
        splitter.addWidget(left_side)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])  # 设置初始大小比例
        
        # 添加所有元素到主布局
        main_layout.addWidget(splitter)
        
        self.setCentralWidget(central_widget)
        
        # 初始化品牌和型号的关联
        if hasattr(self, 'make_combo') and hasattr(self, 'model_combo'):
            self.make_combo.currentTextChanged.connect(self.update_model_options)
            # Initialize model options based on default make
            self.update_model_options(self.make_combo.currentText())
        
        # 设置接受拖放
        self.setAcceptDrops(True)
    
    def add_section_to_custom(self, title, fields):
        group = QGroupBox(title)
        layout = QVBoxLayout()
        
        for label_text, field_name, field_type, options in fields:
            field_layout = QHBoxLayout()
            
            # Add label
            label = QLabel(label_text + ":")
            label.setMinimumWidth(120)
            
            # 创建一个堆叠部件来切换输入方式
            input_stack = QStackedWidget()
            setattr(self, f"{field_name}_stack", input_stack)
            
            # 第一个页面：下拉选项（包括所有特殊选项）
            combo_widget = QWidget()
            combo_layout = QHBoxLayout(combo_widget)
            combo_layout.setContentsMargins(0, 0, 0, 0)
            
            # Add proper input field based on type
            if field_type == "combobox":
                combo = CustomComboBox()
                combo.setMinimumWidth(280)  # 加宽下拉框以容纳更多文本
                
                # 添加特殊选项
                combo.addItem("【随机生成】")  # 随机生成项
                combo.addItem("【不修改】")  # 保留原有项
                combo.addItem("【空数据】")  # 删除此元数据
                combo.addItem("【自定义...】")  # 自定义输入
                
                # 设置特殊选项的工具提示
                combo.setItemData(0, "自动生成符合实际的随机数据", Qt.ToolTipRole)
                combo.setItemData(1, "保留文件中的原始数据不变", Qt.ToolTipRole)
                combo.setItemData(2, "清除已有数据并写入空数据，如文件原本此项为空则依旧空白", Qt.ToolTipRole)
                combo.setItemData(3, "手动输入自定义内容", Qt.ToolTipRole)
                
                # 添加预设选项
                if options:
                    combo.addItems(options)
                
                # 为特殊字段添加更多内容选项
                if field_name == "make":
                    # 确保添加了品牌选项
                    for make in self.metadata_options["make"]:
                        if make not in options:
                            combo.addItem(make)
                
                # 软件选项添加所有可能的软件版本
                elif field_name == "software":
                    # 添加常用移动设备软件
                    common_software = [
                        "iOS 17.2", "iOS 17.1", "iOS 17.0", 
                        "Android 15", "Android 14", "Android 13",
                        "One UI 7.0", "One UI 6.1", "One UI 6.0", 
                        "HarmonyOS 4.0", "HarmonyOS 3.1", 
                        "MIUI 14", "MIUI 13", 
                        "OxygenOS 14", "OxygenOS 13",
                        "ColorOS 14", "ColorOS 13",
                        "Funtouch OS 14", "Funtouch OS 13"
                    ]
                    # 添加常用图片编辑软件
                    photo_software = [
                        "Adobe Photoshop 2024", "Adobe Lightroom Classic 12.5",
                        "Capture One 23", "DxO PhotoLab 7",
                        "Luminar AI", "Affinity Photo 2"
                    ]
                    for software in common_software + photo_software:
                        if software not in options:
                            combo.addItem(software)
                
                # 镜头型号添加常用手机和相机镜头
                elif field_name == "lens_model":
                    # 添加手机设备常用镜头
                    mobile_lenses = [
                        "Wide camera", "Ultra Wide camera", "Telephoto camera",
                        "Periscope Telephoto camera", "Front camera", 
                        "Main camera", "Selfie camera"
                    ]
                    # 添加几款常见相机镜头
                    camera_lenses = [
                        "Canon EF 24-70mm f/2.8L II USM",
                        "Nikon Z 24-70mm f/2.8 S",
                        "Sony FE 24-70mm F2.8 GM II",
                        "ZEISS Otus 55mm f/1.4"
                    ]
                    for lens in mobile_lenses + camera_lenses:
                        if lens not in options:
                            combo.addItem(lens)
                
                # 为各种特殊字段添加工具提示
                if field_name == "exposure_time":
                    for i in range(combo.count()):
                        if i >= 4:  # 跳过特殊选项
                            combo.setItemData(i, "曝光时间，如：1/60秒", Qt.ToolTipRole)
                elif field_name == "fnumber":
                    for i in range(combo.count()):
                        if i >= 4:  # 跳过特殊选项
                            combo.setItemData(i, "光圈大小，如：f/2.8", Qt.ToolTipRole)
                elif field_name == "focal_length":
                    for i in range(combo.count()):
                        if i >= 4:  # 跳过特殊选项
                            combo.setItemData(i, "焦距，如：24mm", Qt.ToolTipRole)
                elif field_name == "iso":
                    for i in range(combo.count()):
                        if i >= 4:  # 跳过特殊选项
                            combo.setItemData(i, "感光度，如：100", Qt.ToolTipRole)
                
                combo.setCurrentIndex(0)  # 默认选择"随机生成"
                combo.currentTextChanged.connect(lambda text, fn=field_name: self.handle_combo_change(text, fn))
                combo.setContextMenuPolicy(Qt.CustomContextMenu)  # 启用自定义右键菜单
                combo.customContextMenuRequested.connect(lambda pos, fn=field_name: self.show_combo_context_menu(pos, fn))
                setattr(self, f"{field_name}_combo", combo)
                
                combo_layout.addWidget(combo)
                input_stack.addWidget(combo_widget)
                
                # 第二个页面：自定义文本输入
                text_widget = QWidget()
                text_layout = QHBoxLayout(text_widget)
                text_layout.setContentsMargins(0, 0, 0, 0)
                
                custom_text = QLineEdit()
                custom_text.setMinimumWidth(200)
                
                # 为不同字段设置不同的占位符文本
                if field_name == "make":
                    custom_text.setPlaceholderText("输入设备品牌，如：Sony")
                elif field_name == "model":
                    custom_text.setPlaceholderText("输入设备型号，如：A7 IV")
                elif field_name == "software":
                    custom_text.setPlaceholderText("输入软件名称，如：Photoshop 2024")
                elif field_name == "lens_model":
                    custom_text.setPlaceholderText("输入镜头型号，如：Sony FE 24-70mm F2.8 GM II")
                elif field_name == "exposure_time":
                    custom_text.setPlaceholderText("输入曝光时间，如：1/60")
                elif field_name == "fnumber":
                    custom_text.setPlaceholderText("输入光圈值，如：2.8")
                elif field_name == "iso":
                    custom_text.setPlaceholderText("输入ISO值，如：100")
                elif field_name == "focal_length":
                    custom_text.setPlaceholderText("输入焦距，如：24mm")
                else:
                    custom_text.setPlaceholderText("输入自定义值...")
                
                button_layout = QHBoxLayout()
                confirm_btn = QPushButton("确认")
                confirm_btn.clicked.connect(lambda checked, fn=field_name: self.confirm_custom_value(fn))
                
                cancel_btn = QPushButton("取消")
                cancel_btn.clicked.connect(lambda checked, fn=field_name: self.cancel_custom_value(fn))
                
                button_layout.addWidget(confirm_btn)
                button_layout.addWidget(cancel_btn)
                
                text_layout.addWidget(custom_text)
                text_layout.addLayout(button_layout)
                input_stack.addWidget(text_widget)
                
                setattr(self, f"{field_name}_custom_text", custom_text)
                
                # Special case for make
                if field_name == "make":
                    self.make_combo = combo
                
                # Special case for model
                if field_name == "model":
                    self.model_combo = combo
                
            elif field_type == "text":
                # 对于纯文本字段，使用结合了下拉菜单和文本输入的自定义组件
                combo_text_widget = QWidget()
                combo_text_layout = QHBoxLayout(combo_text_widget)
                combo_text_layout.setContentsMargins(0, 0, 0, 0)
                
                # 添加类型选择下拉框
                type_combo = CustomComboBox()  # 使用自定义ComboBox替代普通ComboBox
                type_combo.addItem("【随机生成】")
                type_combo.addItem("【不修改】")
                type_combo.addItem("【空数据】")
                type_combo.addItem("自定义输入")
                
                # 设置工具提示
                type_combo.setItemData(0, "自动生成符合实际的随机数据", Qt.ToolTipRole)
                type_combo.setItemData(1, "保留文件中的原始数据不变", Qt.ToolTipRole)
                type_combo.setItemData(2, "清除已有数据并写入空数据，如文件原本此项为空则依旧空白", Qt.ToolTipRole)
                type_combo.setItemData(3, "手动输入自定义内容", Qt.ToolTipRole)
                
                type_combo.setCurrentIndex(0)
                setattr(self, f"{field_name}_type_combo", type_combo)
                
                # 添加文本输入框
                text = QLineEdit()
                text.setMinimumWidth(150)
                
                # 为不同字段设置不同的占位符文本
                if field_name == "date_time_original" or field_name == "create_date" or field_name == "modify_date":
                    text.setPlaceholderText("格式：YYYY:MM:DD HH:MM:SS")
                elif field_name == "gps_latitude" or field_name == "gps_longitude":
                    text.setPlaceholderText("格式：数字（如：34.0522）")
                elif field_name == "gps_altitude":
                    text.setPlaceholderText("格式：数字，单位米（如：100）")
                elif field_name == "gps_time_stamp":
                    text.setPlaceholderText("格式：HH:MM:SS")
                elif field_name == "gps_date_stamp":
                    text.setPlaceholderText("格式：YYYY:MM:DD")
                elif field_name == "creator":
                    text.setPlaceholderText("输入创作者姓名")
                elif field_name == "copyright_notice":
                    text.setPlaceholderText("输入版权信息，如：(C)2023 摄影师")
                elif field_name == "description":
                    text.setPlaceholderText("输入图片描述")
                elif field_name == "title":
                    text.setPlaceholderText("输入图片标题")
                elif field_name == "keywords":
                    text.setPlaceholderText("输入关键词，用逗号分隔")
                elif field_name == "location":
                    text.setPlaceholderText("输入拍摄地点")
                else:
                    text.setPlaceholderText("输入自定义值...")
                
                text.setEnabled(False)  # 默认禁用
                setattr(self, f"{field_name}_text", text)
                
                # 连接类型选择变化信号
                type_combo.currentTextChanged.connect(lambda text, fn=field_name: self.handle_text_type_change(text, fn))
                
                combo_text_layout.addWidget(type_combo)
                combo_text_layout.addWidget(text)
                
                input_stack.addWidget(combo_text_widget)
            
            field_layout.addWidget(label)
            field_layout.addWidget(input_stack)
            
            layout.addLayout(field_layout)
        
        group.setLayout(layout)
        self.custom_layout.addWidget(group)
    
    def handle_text_type_change(self, selection, field_name):
        """处理文本字段类型选择变化"""
        if hasattr(self, f"{field_name}_text"):
            text_field = getattr(self, f"{field_name}_text")
            
            if selection == "自定义输入":
                text_field.setEnabled(True)
                text_field.clear()
                text_field.setFocus()
            else:
                text_field.setEnabled(False)
                text_field.setText("")
    
    def show_combo_context_menu(self, pos, field_name):
        """显示下拉框的右键菜单"""
        combo = getattr(self, f"{field_name}_combo")
        
        # 获取当前项的索引和文本
        current_index = combo.currentIndex()
        current_text = combo.currentText()
        
        # 创建右键菜单
        menu = QMenu()
        
        # 特殊选项，不能删除
        predefined_values = ["【随机生成】", "【不修改】", "【空数据】", "【自定义...】"]
        
        # 创建删除选项
        if current_index >= 4 and current_text not in predefined_values:  # 跳过前4个特殊选项
            delete_action = QAction("删除此选项", self)
            delete_action.triggered.connect(lambda: self.delete_custom_item(field_name, current_index))
            menu.addAction(delete_action)
        
        # 创建新增自定义选项
        add_action = QAction("添加自定义选项...", self)
        add_action.triggered.connect(lambda: self.add_custom_item(field_name))
        menu.addAction(add_action)
        
        # 创建清除所有自定义选项
        clear_action = QAction("清除所有自定义选项", self)
        clear_action.triggered.connect(lambda: self.clear_custom_items(field_name))
        menu.addAction(clear_action)
        
        # 显示分隔线
        menu.addSeparator()
        
        # 显示套用常用选项子菜单
        common_values_menu = menu.addMenu("使用常用值")
        
        # 根据不同字段添加常用值
        if field_name == "make":
            common_values = ["Apple", "Samsung", "Huawei", "Xiaomi", "Google", "Canon", "Nikon", "Sony"]
        elif field_name == "white_balance":
            common_values = ["自动", "日光", "阴天", "钨丝灯", "荧光灯"]
        elif field_name == "lens_model":
            common_values = ["Wide camera", "Ultra Wide camera", "Telephoto camera", "Prime Lens", "Zoom Lens"]
        else:
            common_values = []
            
        for value in common_values:
            action = common_values_menu.addAction(value)
            action.triggered.connect(lambda checked, v=value: self.apply_common_value(field_name, v))
        
        # 显示菜单
        if menu.actions():
            menu.exec_(QCursor.pos())
    
    def handle_combo_change(self, text, field_name):
        """处理下拉菜单选择变化，自定义选项时切换到文本输入"""
        if text == "【自定义...】":
            # 切换到自定义文本输入界面
            stack = getattr(self, f"{field_name}_stack")
            stack.setCurrentIndex(1)  # 切换到文本输入界面
            
            # 设置焦点到文本输入框
            custom_text = getattr(self, f"{field_name}_custom_text")
            custom_text.clear()
            custom_text.setFocus()
        
        # 如果是品牌字段发生变化，更新相关联字段
        if field_name == "make":
            # 保存当前镜头型号的选择，特别是空数据选项
            current_lens_selection = None
            if hasattr(self, "lens_model_combo"):
                current_lens_selection = self.lens_model_combo.currentText()
                
            # 更新相关联字段
            self.update_model_options(text)
            self.update_software_options(text)
            self.update_lens_model_options(text)
            
            # 如果镜头型号原本是空数据，尝试保持此设置
            if current_lens_selection == "【空数据】" and hasattr(self, "lens_model_combo"):
                lens_empty_index = self.lens_model_combo.findText("【空数据】")
                if lens_empty_index >= 0:
                    self.lens_model_combo.setCurrentIndex(lens_empty_index)
                    print("品牌变更后保持镜头型号为【空数据】")
    
    def update_model_options(self, make):
        """根据选择的相机品牌更新型号下拉框选项"""
        
        # 清除当前所有项目
        self.model_combo.clear()
        
        # 首先添加特殊选项
        for option in self.special_options:
            self.model_combo.addItem(option)
        
        # 如果选择了"空数据"选项，则不添加其他型号
        if make == "空数据":
            return
            
        # 如果品牌在我们的数据中，添加对应的型号
        if make in self.metadata_options["model"]:
            models = self.metadata_options["model"][make]
            for model in models:
                self.model_combo.addItem(model)
        
        # 同时更新软件和镜头型号选项以匹配品牌
        self.update_software_options(make)
        self.update_lens_model_options(make)
    
    def update_software_options(self, make):
        """根据选择的相机品牌更新软件下拉框选项"""
        # 清除当前所有项目
        self.software_combo.clear()
        
        # 首先添加特殊选项
        for option in self.special_options:
            self.software_combo.addItem(option)
        
        # 如果选择了"空数据"选项，则不添加其他软件
        if make == "空数据":
            return
            
        # 根据品牌添加相关软件
        if make == "Apple":
            software_list = [s for s in self.metadata_options["software"] if s.startswith("iOS")]
        elif make == "Samsung":
            software_list = [s for s in self.metadata_options["software"] if s.startswith("One UI")]
        elif make == "Huawei":
            software_list = [s for s in self.metadata_options["software"] if s.startswith("HarmonyOS") or s.startswith("EMUI")]
        elif make == "Xiaomi":
            software_list = [s for s in self.metadata_options["software"] if s.startswith("MIUI")]
        elif make == "Google":
            software_list = [s for s in self.metadata_options["software"] if s.startswith("Android")]
        else:
            software_list = self.metadata_options["software"]
        
        # 添加过滤后的软件选项
        for software in software_list:
            self.software_combo.addItem(software)
    
    def update_lens_model_options(self, make):
        """根据选择的相机品牌更新镜头型号下拉框选项"""
        # 如果当前已设置为空数据，保留此设置（避免被覆盖）
        if hasattr(self, "lens_model_combo") and self.lens_model_combo.currentText() == "【空数据】":
            # 用户已明确选择空数据，不更改其选择
            print("保留镜头型号为【空数据】的设置")
            return
        
        # 清除当前所有项目
        self.lens_model_combo.clear()
        
        # 首先添加特殊选项
        for option in self.special_options:
            self.lens_model_combo.addItem(option)
        
        # 如果选择了"空数据"选项，则不添加其他镜头型号
        if make == "【空数据】":
            return
            
        # 根据品牌添加相关镜头型号
        if make in ["Apple", "Samsung", "Huawei", "Xiaomi", "Google", "OnePlus", "OPPO", "Vivo"]:
            # 移动设备品牌使用移动镜头术语
            lens_list = ["Wide camera", "Ultra Wide camera", "Telephoto camera", "Front camera", "Main camera", "Selfie camera"]
        elif make in ["Canon", "Nikon", "Sony", "Fujifilm", "Olympus", "Pentax", "Leica"]:
            # 相机品牌使用带有品牌名称的特定镜头
            brand_lens_prefix = f"{make} "
            lens_list = [l for l in self.metadata_options["lens_model"] if l.startswith(brand_lens_prefix) or "mm" in l]
            if not lens_list:  # 如果没有找到特定品牌的镜头，使用所有镜头
                lens_list = self.metadata_options["lens_model"]
        else:
            lens_list = self.metadata_options["lens_model"]
        
        # 添加过滤后的镜头型号选项
        for lens in lens_list:
            self.lens_model_combo.addItem(lens)
    
    def browse_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", "", "图片文件 (*.jpg *.jpeg *.png *.tiff *.heic *.webp *.bmp)"
        )
        if file_paths:
            self.add_files(file_paths)
    
    def add_files(self, file_paths):
        """添加文件到列表，使用自定义项目支持复选框"""
        # 过滤掉已经添加的文件
        new_files = [path for path in file_paths if path not in self.file_paths]
        
        # 如果没有新文件，直接返回
        if not new_files:
            return
        
        # 添加新文件到列表和UI
        for file_path in new_files:
            # 添加到内部存储
            self.file_paths.append(file_path)
            
            # 创建自定义列表项
            item_widget = FileListItem(file_path)
            
            # 添加到QListWidget
            list_item = QListWidgetItem()
            self.file_list.addItem(list_item)
            self.file_list.setItemWidget(list_item, item_widget)
            
            # 设置项高度
            list_item.setSizeHint(item_widget.sizeHint())
        
        # 更新进度标签
        self.update_progress_label()
        
        # 选择第一个文件并更新预览
        if self.file_list.count() > 0 and not self.current_file_path:
            self.current_file_path = self.file_paths[0]
            self.update_image_preview(self.current_file_path)
    
    def clear_file_list(self):
        """清除文件列表"""
        if self.file_list.count() == 0:
            return
            
        reply = QMessageBox.question(
            self, 
            "确认清除", 
            "确定要清除所有已选择的文件吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.file_list.clear()
            self.file_paths = []
            self.current_file_path = ""
            self.image_preview.setText("选择图片后显示预览\n支持拖放图片到此处")
            self.image_info.setText("")
            self.update_progress_label()
    
    def on_file_clicked(self, item):
        """当点击文件项时，显示预览而不是选中/取消选中"""
        # 获取对应的自定义widget
        item_widget = self.file_list.itemWidget(item)
        if item_widget:
            # 更新当前文件路径
            file_path = item_widget.file_path
            self.current_file_path = file_path
            
            # 更新预览
            self.update_image_preview(file_path)
    
    def get_checked_files(self):
        """获取所有被选中的文件路径"""
        checked_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item_widget = self.file_list.itemWidget(item)
            if item_widget and item_widget.checkbox.isChecked():
                checked_files.append(item_widget.file_path)
        return checked_files
    
    def select_all_files(self):
        """选中所有文件"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item_widget = self.file_list.itemWidget(item)
            if item_widget:
                item_widget.checkbox.setChecked(True)
    
    def invert_file_selection(self):
        """反转所有文件的选择状态"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item_widget = self.file_list.itemWidget(item)
            if item_widget:
                current_state = item_widget.checkbox.isChecked()
                item_widget.checkbox.setChecked(not current_state)
    
    def update_progress_label(self):
        """更新进度标签"""
        total_count = self.file_list.count()
        checked_count = len(self.get_checked_files())
        
        if total_count == 0:
            self.progress_label.setText("")
        else:
            self.progress_label.setText(f"已添加: {total_count} 个文件, 已选中: {checked_count} 个文件")
    
    def show_sort_menu(self):
        """显示排序菜单"""
        sort_menu = QMenu(self)
        
        # 按文件大小排序
        size_asc_action = QAction("按文件大小从小到大", self)
        size_asc_action.triggered.connect(lambda: self.sort_files("size_asc"))
        sort_menu.addAction(size_asc_action)
        
        size_desc_action = QAction("按文件大小从大到小", self)
        size_desc_action.triggered.connect(lambda: self.sort_files("size_desc"))
        sort_menu.addAction(size_desc_action)
        
        # 按修改日期排序
        date_asc_action = QAction("按修改日期从早到晚", self)
        date_asc_action.triggered.connect(lambda: self.sort_files("date_asc"))
        sort_menu.addAction(date_asc_action)
        
        date_desc_action = QAction("按修改日期从晚到早", self)
        date_desc_action.triggered.connect(lambda: self.sort_files("date_desc"))
        sort_menu.addAction(date_desc_action)
        
        # 按文件名排序
        name_asc_action = QAction("按文件名字母升序", self)
        name_asc_action.triggered.connect(lambda: self.sort_files("name_asc"))
        sort_menu.addAction(name_asc_action)
        
        name_desc_action = QAction("按文件名字母降序", self)
        name_desc_action.triggered.connect(lambda: self.sort_files("name_desc"))
        sort_menu.addAction(name_desc_action)
        
        # 显示菜单
        sort_menu.exec_(QCursor.pos())
    
    def sort_files(self, sort_type):
        """根据指定的排序类型对文件列表进行排序"""
        if not self.file_paths or self.file_list.count() == 0:
            return
            
        # 收集当前所有文件信息（路径和选择状态）
        file_items = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item_widget = self.file_list.itemWidget(item)
            if item_widget:
                file_items.append({
                    'path': item_widget.file_path,
                    'checked': item_widget.checkbox.isChecked()
                })
        
        # 根据排序类型对文件进行排序
        if sort_type == "size_asc":
            file_items.sort(key=lambda x: os.path.getsize(x['path']))
        elif sort_type == "size_desc":
            file_items.sort(key=lambda x: os.path.getsize(x['path']), reverse=True)
        elif sort_type == "date_asc":
            file_items.sort(key=lambda x: os.path.getmtime(x['path']))
        elif sort_type == "date_desc":
            file_items.sort(key=lambda x: os.path.getmtime(x['path']), reverse=True)
        elif sort_type == "name_asc":
            file_items.sort(key=lambda x: os.path.basename(x['path']).lower())
        elif sort_type == "name_desc":
            file_items.sort(key=lambda x: os.path.basename(x['path']).lower(), reverse=True)
        
        # 清除当前列表并重建
        sorted_file_paths = [item['path'] for item in file_items]
        self.file_list.clear()
        self.file_paths = sorted_file_paths
        
        # 重新添加排序后的文件到列表
        for item in file_items:
            file_path = item['path']
            item_widget = FileListItem(file_path)
            item_widget.checkbox.setChecked(item['checked'])
            
            list_item = QListWidgetItem()
            self.file_list.addItem(list_item)
            self.file_list.setItemWidget(list_item, item_widget)
            list_item.setSizeHint(item_widget.sizeHint())
        
        # 更新进度标签
        self.update_progress_label()
    
    def update_image_preview(self, file_path):
        """更新图片预览和图片信息"""
        if not file_path or not os.path.exists(file_path):
            self.image_preview.setText("图片不存在或无法访问")
            self.image_info.setText("")
            return
            
        try:
            # 调试信息 - 输出文件路径和扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            print(f"正在加载图片: {file_path}, 扩展名: {file_ext}")
            
            # 设置图片加载中提示
            self.image_preview.setText("正在加载图片...")
            QApplication.processEvents()  # 刷新UI
            
            pixmap = None
            
            # 针对不同格式使用不同加载方法
            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                # 这些是Qt原生支持较好的格式
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    print(f"使用Qt原生方法成功加载图片")
            
            # 如果Qt加载失败或是其他格式，尝试用PIL加载
            if (pixmap is None or pixmap.isNull()) and HAS_PIL:
                try:
                    print(f"尝试使用PIL加载图片...")
                    # 用PIL打开图片
                    pil_image = Image.open(file_path)
                    
                    # 调试信息
                    print(f"PIL成功打开图片，模式: {pil_image.mode}, 尺寸: {pil_image.size}")
                    
                    # 转换为RGB模式(如果是RGBA或其他模式)
                    if pil_image.mode != 'RGB' and pil_image.mode != 'RGBA':
                        pil_image = pil_image.convert('RGB')
                        print(f"转换图片到RGB模式")
                    
                    # 转换为QImage
                    if pil_image.mode == 'RGB':
                        data = pil_image.tobytes('raw', 'RGB')
                        q_image = QImage(data, pil_image.width, pil_image.height, pil_image.width * 3, QImage.Format_RGB888)
                    else:  # RGBA模式
                        data = pil_image.tobytes('raw', 'RGBA')
                        q_image = QImage(data, pil_image.width, pil_image.height, pil_image.width * 4, QImage.Format_RGBA8888)
                    
                    # 转换为QPixmap
                    pixmap = QPixmap.fromImage(q_image)
                    
                    print(f"使用PIL成功转换图片为QPixmap, 大小: {pixmap.width()}x{pixmap.height()}")
                except Exception as e:
                    print(f"PIL加载图片失败: {e}")
                    pixmap = None
            
            # 如果尝试了上述方法，但仍然加载失败，最后直接使用Qt尝试加载
            if pixmap is None or pixmap.isNull():
                print("尝试最后的Qt直接加载方式...")
                pixmap = QPixmap(file_path)
            
            # 如果加载失败
            if pixmap is None or pixmap.isNull():
                error_msg = f"无法加载图片格式: {file_ext}\n请确保安装了Pillow库: pip install Pillow"
                if file_ext.lower() in ['.jpg', '.jpeg', '.png']:
                    error_msg += f"\n\n常见格式加载失败，请尝试:\n1. 确认文件未损坏\n2. 重新启动程序\n3. 更新PyQt5和Pillow库"
                
                self.image_preview.setText(error_msg)
                self.image_info.setText("")
                print(f"所有方法均无法加载图片!")
                return
                
            # 获取图片信息
            file_size = os.path.getsize(file_path) / 1024  # KB
            if file_size > 1024:
                file_size = file_size / 1024  # 转换为MB
                size_str = f"{file_size:.2f} MB"
            else:
                size_str = f"{file_size:.1f} KB"
                
            img_width = pixmap.width()
            img_height = pixmap.height()
            
            # 调整图片大小以适应预览区域
            preview_size = min(self.image_preview.width() - 20, self.image_preview.height() - 20)
            preview_pixmap = pixmap.scaled(
                preview_size, 
                preview_size,
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # 显示图片
            self.image_preview.setPixmap(preview_pixmap)
            
            # 显示基本图片信息
            info_text = f"文件名: {os.path.basename(file_path)}\n"
            info_text += f"格式: {file_ext.upper().replace('.','')}\n"
            info_text += f"尺寸: {img_width} x {img_height} 像素\n"
            info_text += f"大小: {size_str}"
            
            # 获取元数据并显示主要信息
            self.current_metadata = self.get_file_metadata(file_path)
            if self.current_metadata:
                # 添加主要元数据到预览
                if "EXIF:Make" in self.current_metadata:
                    info_text += f"\n设备: {self.current_metadata.get('EXIF:Make', '')} {self.current_metadata.get('EXIF:Model', '')}"
                if "EXIF:LensModel" in self.current_metadata:
                    info_text += f"\n镜头: {self.current_metadata.get('EXIF:LensModel', '')}"
                if "EXIF:DateTimeOriginal" in self.current_metadata:
                    info_text += f"\n拍摄时间: {self.current_metadata.get('EXIF:DateTimeOriginal', '')}"
                if "EXIF:ExposureTime" in self.current_metadata:
                    info_text += f"\n曝光: {self.current_metadata.get('EXIF:ExposureTime', '')} 秒, f/{self.current_metadata.get('EXIF:FNumber', '')}, ISO {self.current_metadata.get('EXIF:ISO', '')}"
            
            self.image_info.setText(info_text)
            
            # 为图片预览添加工具提示，显示完整元数据
            if self.current_metadata:
                self.image_preview.setToolTip(self.format_metadata_tooltip(self.current_metadata))
                # 安装事件过滤器用于自定义悬停提示
                self.image_preview.installEventFilter(self)
            
        except Exception as e:
            self.image_preview.setText(f"加载图片预览时出错: {str(e)}\n尝试安装Pillow库: pip install Pillow")
            self.image_info.setText("")
            import traceback
            traceback.print_exc()  # 打印详细错误信息
    
    def get_file_metadata(self, file_path):
        """获取文件的元数据"""
        if not self.exiftool_path or not os.path.exists(self.exiftool_path) or not file_path or not os.path.exists(file_path):
            return None
            
        try:
            with exiftool.ExifToolHelper(executable=self.exiftool_path) as et:
                metadata = et.get_metadata(file_path)[0]
                return metadata
        except Exception as e:
            print(f"读取元数据时出错: {e}")
            return None
            
    def format_metadata_tooltip(self, metadata):
        """将完整元数据格式化为工具提示"""
        if not metadata:
            return "无可用元数据"
            
        # 按分类整理元数据
        categories = {
            "基本信息": ["SourceFile", "FileName", "FileSize", "FileType", "FileModifyDate"],
            "相机信息": ["Make", "Model", "LensModel", "Software"],
            "拍摄参数": ["ExposureTime", "FNumber", "ISO", "FocalLength", "WhiteBalance", "Flash", "ExposureMode"],
            "时间信息": ["DateTimeOriginal", "CreateDate", "ModifyDate"],
            "GPS信息": ["GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"],
            "其他信息": []
        }
        
        # 整理元数据
        tooltip_parts = []
        
        for category, keys in categories.items():
            category_items = []
            for key in keys:
                # 添加带前缀的完整键名(如EXIF:Make)
                for full_key in metadata:
                    if full_key.endswith(":" + key) and metadata[full_key]:
                        category_items.append(f"{key}: {metadata[full_key]}")
                        break
            
            # 如果该分类有内容，添加到工具提示
            if category_items:
                tooltip_parts.append(f"【{category}】")
                tooltip_parts.extend(category_items)
                tooltip_parts.append("")  # 添加空行作为分隔
        
        # 添加未分类的其他元数据
        other_items = []
        for key, value in metadata.items():
            if value and not any(key.endswith(":" + k) for c in categories.values() for k in c):
                # 简化键名 - 去掉前缀如EXIF:
                simple_key = key.split(":")[-1] if ":" in key else key
                if simple_key not in [k for c in categories.values() for k in c]:
                    other_items.append(f"{simple_key}: {value}")
                    
        if other_items:
            tooltip_parts.append("【其他信息】")
            # 限制数量避免提示过长
            if len(other_items) > 10:
                tooltip_parts.extend(other_items[:10])
                tooltip_parts.append(f"...以及{len(other_items)-10}个其他项")
            else:
                tooltip_parts.extend(other_items)
                
        return "\n".join(tooltip_parts)
        
    def eventFilter(self, obj, event):
        """事件过滤器，用于实现自定义的元数据悬停提示"""
        if obj == self.image_preview and self.current_file_path and event.type() == QEvent.ToolTip:
            # 显示自定义悬停提示
            if hasattr(self, 'current_metadata') and self.current_metadata:
                tooltip_text = self.format_metadata_tooltip(self.current_metadata)
                QToolTip.showText(event.globalPos(), tooltip_text)
                return True
                
        return super().eventFilter(obj, event)
    
    def generate_random_metadata(self):
        """为所选文件生成随机元数据"""
        # 获取通过复选框选中的文件
        checked_files = self.get_checked_files()
        
        # 确保有选中的文件
        if not checked_files:
            QMessageBox.warning(self, "提示", "请至少选中一个文件")
            return
            
        # 应用到所选文件
        if len(checked_files) > 1:
            # 批量处理 - 创建进度对话框
            progress_dialog = QProgressDialog("正在应用随机元数据...", "取消", 0, len(checked_files), self)
            progress_dialog.setWindowTitle("处理中")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            
            # 存储所有处理结果和每个文件的元数据
            all_results = []
            all_metadata = {}
            
            try:
                for i, file_path in enumerate(checked_files):
                    # 更新进度
                    progress_dialog.setValue(i)
                    progress_dialog.setLabelText(f"正在处理 ({i+1}/{len(checked_files)}): {os.path.basename(file_path)}")
                    QApplication.processEvents()
                    
                    # 检查用户是否取消
                    if progress_dialog.wasCanceled():
                        break
                    
                    # 为每个文件创建独立的随机元数据
                    random_metadata = self.create_random_metadata()
                    
                    # 为这个文件生成特定的变化（时间戳、GPS等轻微随机化）
                    slightly_varied_metadata = self.slightly_vary_metadata(random_metadata, file_path)
                    
                    # 存储每个文件的元数据用于批处理预览
                    all_metadata[file_path] = slightly_varied_metadata
                    
                    # 应用元数据并获取结果
                    result = self._apply_metadata_to_file(file_path, slightly_varied_metadata)
                    # 记录处理结果
                    all_results.append((file_path, result, slightly_varied_metadata))
            finally:
                # 确保进度对话框关闭
                progress_dialog.setValue(len(checked_files))  # 确保进度条到达100%
                progress_dialog.close()
                QApplication.processEvents()  # 立即处理所有待处理的事件，确保对话框关闭
                progress_dialog.deleteLater()
            
            # 显示一个总结性的成功消息
            self._show_batch_results(all_results, "随机模式")
        else:
            # 单个文件处理
            file_path = checked_files[0]
            
            # 为单个文件创建独立的随机元数据
            random_metadata = self.create_random_metadata()
            
            # 为文件生成特定的随机元数据（微调）
            slightly_varied_metadata = self.slightly_vary_metadata(random_metadata, file_path)
            
            # 应用元数据
            result = self._apply_metadata_to_file(file_path, slightly_varied_metadata)
            
            # 显示结果
            if result:
                QMessageBox.information(self, "成功", f"随机元数据已成功应用到文件:\n{os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "失败", f"无法应用随机元数据到文件:\n{os.path.basename(file_path)}")
    
    def _show_batch_results(self, results, mode_name):
        """显示批量处理结果的总结对话框
        results: 元组列表 [(file_path, result, metadata), ...]
        mode_name: 模式名称，例如"随机模式"或"自定义模式"
        """
        if not results:
            return
            
        # 计算成功和失败的数量
        success_count = sum(1 for _, result, _ in results if result)
        failed_count = len(results) - success_count
        
        # 创建结果文本
        result_text = f"批量处理完成\n\n成功: {success_count} 个文件\n"
        if failed_count > 0:
            result_text += f"失败: {failed_count} 个文件\n"
        
        # 添加详细信息
        details_text = "详细信息:\n\n"
        for file_path, result, metadata in results:
            file_name = os.path.basename(file_path)
            file_info = os.stat(file_path)
            file_size = self._format_file_size(file_info.st_size)
            mod_time = datetime.datetime.fromtimestamp(file_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            
            status = "成功" if result else "失败"
            details_text += f"文件: {file_name}\n"
            details_text += f"状态: {status}\n"
            details_text += f"路径: {file_path}\n"
            details_text += f"大小: {file_size}\n"
            details_text += f"修改时间: {mod_time}\n"
            
            if result:
                # 添加应用的元数据摘要（更详细）
                details_text += f"应用的元数据:\n"
                
                # 设备信息
                if any(key in metadata for key in ["Make", "Model", "Software", "LensModel"]):
                    details_text += "== 设备信息 ==\n"
                    for key in ["Make", "Model", "Software", "LensModel"]:
                        if key in metadata and metadata[key]:
                            details_text += f"  {key}: {metadata[key]}\n"
                
                # 拍摄参数
                if any(key in metadata for key in ["ExposureTime", "FNumber", "ISO", "FocalLength", "WhiteBalance", "Flash", "Orientation"]):
                    details_text += "== 拍摄参数 ==\n"
                    for key in ["ExposureTime", "FNumber", "ISO", "FocalLength", "WhiteBalance", "Flash", "Orientation"]:
                        if key in metadata and metadata[key]:
                            details_text += f"  {key}: {metadata[key]}\n"
                
                # 日期信息
                if any(key in metadata for key in ["DateTimeOriginal", "CreateDate", "ModifyDate"]):
                    details_text += "== 日期信息 ==\n"
                    for key in ["DateTimeOriginal", "CreateDate", "ModifyDate"]:
                        if key in metadata and metadata[key]:
                            details_text += f"  {key}: {metadata[key]}\n"
                
                # GPS信息
                gps_keys = ["GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef", 
                           "GPSAltitude", "GPSAltitudeRef", "GPSTimeStamp", "GPSDateStamp"]
                if any(key in metadata for key in gps_keys):
                    details_text += "== GPS信息 ==\n"
                    for key in gps_keys:
                        if key in metadata and metadata[key]:
                            details_text += f"  {key}: {metadata[key]}\n"
                
                # 其他信息
                other_keys = ["Creator", "Copyright", "Description", "Title", "Keywords", "Location"]
                if any(key in metadata for key in other_keys):
                    details_text += "== 其他信息 ==\n"
                    for key in other_keys:
                        if key in metadata and metadata[key]:
                            details_text += f"  {key}: {metadata[key]}\n"
            else:
                details_text += "应用失败，无法写入元数据。请检查文件权限或格式是否支持。\n"
            
            details_text += "--------------------------------\n\n"
        
        # 创建自定义对话框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"{mode_name}处理结果")
        msg_box.setText(result_text)
        msg_box.setDetailedText(details_text)
        
        # 设置更大的尺寸
        msg_box.setMinimumWidth(600)
        
        # 替换标准按钮为中文按钮
        ok_button = msg_box.addButton("确定", QMessageBox.AcceptRole)
        msg_box.setDefaultButton(ok_button)
        
        # 修改系统生成的"Show Details..."按钮文本为中文
        for button in msg_box.buttons():
            if msg_box.buttonRole(button) == QMessageBox.ActionRole:
                button.setText("显示详情...")
        
        # 显示对话框
        msg_box.exec_()
        
        # 手动设置文本编辑区域的大小
        detail_text_edit = msg_box.findChild(QTextEdit)
        if detail_text_edit:
            detail_text_edit.setMinimumSize(600, 500)
    
    def _format_file_size(self, size_in_bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} TB"
    
    def apply_custom_metadata(self):
        """应用自定义模式下的元数据到所选文件"""
        # 获取通过复选框选中的文件
        checked_files = self.get_checked_files()
        
        # 确保有选中的文件
        if not checked_files:
            QMessageBox.warning(self, "提示", "请至少选中一个文件")
            return
            
        # 收集自定义元数据（基础模板）
        custom_metadata_template = self.collect_custom_metadata()
            
        # 批量处理多个文件
        if len(checked_files) > 1:
            # 创建每个文件的元数据
            all_metadata = {}
            
            # 为每个文件单独生成随机值
            for file_path in checked_files:
                # 复制基本模板
                file_metadata = custom_metadata_template.copy()
                
                # 为所有标记为随机生成的字段生成独立的随机值
                # 创建独立的随机元数据基础
                random_metadata = self.create_random_metadata()
                
                # 填充所有标记为随机的字段
                for key, value in file_metadata.items():
                    if value is None and key in random_metadata:  # None表示随机生成
                        file_metadata[key] = random_metadata[key]
                
                # 添加微小变化使其更真实
                varied_metadata = self.slightly_vary_metadata(file_metadata, file_path)
                all_metadata[file_path] = varied_metadata
            
            # 显示批量预览
            self._show_batch_preview(all_metadata, "自定义")
        else:
            # 单个文件处理
            file_path = checked_files[0]
            
            # 处理所有设置为随机的字段
            file_metadata = custom_metadata_template.copy()
            random_metadata = self.create_random_metadata()
            for key, value in file_metadata.items():
                if value is None and key in random_metadata:  # None表示随机生成
                    file_metadata[key] = random_metadata[key]
                    
            # 添加微小变化使其更真实
            varied_metadata = self.slightly_vary_metadata(file_metadata, file_path)
            
            # 显示预览和确认
            msg = QMessageBox()
            msg.setWindowTitle("预览自定义元数据")
            msg.setText(f"将应用以下自定义元数据到 {os.path.basename(file_path)}")
            
            # 格式化元数据预览为可读形式
            preview_text = self.format_metadata_for_preview(varied_metadata)
            msg.setDetailedText(preview_text)
            
            # 设置更大的尺寸
            msg.setMinimumWidth(600)
            
            # 自定义按钮
            apply_button = msg.addButton("应用", QMessageBox.ApplyRole)
            cancel_button = msg.addButton("取消", QMessageBox.RejectRole)
            msg.setDefaultButton(apply_button)
            
            # 修改"显示详情"按钮文本
            for button in msg.buttons():
                if msg.buttonRole(button) == QMessageBox.ActionRole:
                    button.setText("查看详情...")
            
            # 显示对话框
            result = msg.exec_()
            
            # 手动设置文本编辑区域的大小
            detail_text_edit = msg.findChild(QTextEdit)
            if detail_text_edit:
                detail_text_edit.setMinimumSize(500, 400)
            
            # 应用元数据
            if msg.clickedButton() == apply_button:
                # 应用元数据
                result = self._apply_metadata_to_file(file_path, varied_metadata)
                
                # 显示结果消息
                if result:
                    QMessageBox.information(self, "成功", f"自定义元数据已成功应用到文件:\n{os.path.basename(file_path)}")
                else:
                    QMessageBox.warning(self, "失败", f"无法应用自定义元数据到文件:\n{os.path.basename(file_path)}")
    
    def create_random_metadata(self):
        """创建随机元数据的辅助方法"""
        # 复制当前的generate_random_metadata方法的逻辑，但仅返回元数据，不进行应用
        make = random.choice(self.metadata_options["make"])
        model = random.choice(self.metadata_options["model"][make])
        
        # 为选择的品牌选择合适的软件
        software = None
        if make == "Apple":
            software = random.choice([s for s in self.metadata_options["software"] if s.startswith("iOS")])
        elif make == "Samsung":
            software = random.choice([s for s in self.metadata_options["software"] if s.startswith("One UI")])
        elif make == "Huawei":
            software = random.choice([s for s in self.metadata_options["software"] if s.startswith("HarmonyOS") or s.startswith("EMUI")])
        elif make == "Xiaomi":
            software = random.choice([s for s in self.metadata_options["software"] if s.startswith("MIUI")])
        elif make == "Google":
            software = random.choice([s for s in self.metadata_options["software"] if s.startswith("Android")])
        else:
            software = random.choice(self.metadata_options["software"])
        
        # 为选择的品牌选择合适的镜头型号
        lens_model = None
        if make in ["Apple", "Samsung", "Huawei", "Xiaomi", "Google", "OnePlus", "OPPO", "Vivo"]:
            # 移动设备品牌使用移动镜头术语
            mobile_lenses = ["Wide camera", "Ultra Wide camera", "Telephoto camera", "Front camera", "Main camera", "Selfie camera"]
            lens_model = random.choice(mobile_lenses)
        elif make in ["Canon", "Nikon", "Sony", "Fujifilm", "Olympus", "Pentax", "Leica"]:
            # 相机品牌使用带有品牌名称的特定镜头
            brand_lens_prefix = f"{make} "
            lens_options = [l for l in self.metadata_options["lens_model"] if l.startswith(brand_lens_prefix) or "mm" in l]
            if lens_options:
                lens_model = random.choice(lens_options)
            else:
                lens_model = random.choice(self.metadata_options["lens_model"])
        else:
            lens_model = random.choice(self.metadata_options["lens_model"])
        
        # Random date within the last 3 years
        days_ago = random.randint(0, 365 * 3)
        random_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        date_string = random_date.strftime("%Y:%m:%d %H:%M:%S")
        
        # Random GPS coordinates (roughly covering populated areas)
        latitude = random.uniform(-60, 70)
        longitude = random.uniform(-180, 180)
        altitude = random.uniform(0, 3000)
        lat_ref = "N" if latitude >= 0 else "S"
        lon_ref = "E" if longitude >= 0 else "W"
        
        # 随机选择中文选项然后映射到英文
        white_balance_cn = random.choice(self.metadata_options_cn["white_balance"])
        flash_cn = random.choice(self.metadata_options_cn["flash"])
        
        white_balance_map = {
            "自动": "Auto", "手动": "Manual", "日光": "Daylight", 
            "阴天": "Cloudy", "钨丝灯": "Tungsten", "荧光灯": "Fluorescent"
        }
        
        flash_map = {
            "无闪光灯": "No Flash", "闪光灯已触发": "Flash Fired", 
            "闪光灯未触发": "Flash Not Fired", "自动闪光灯": "Auto Flash", 
            "红眼减轻": "Red-eye Reduction"
        }
        
        # Generate all metadata
        metadata = {
            # EXIF Camera Info
            "Make": make,
            "Model": model,
            "Software": software,
            "LensModel": lens_model,
            "ExposureTime": random.choice(self.metadata_options["exposure_time"]),
            "FNumber": random.choice(self.metadata_options["fnumber"]),
            "ISO": random.choice(self.metadata_options["iso"]),
            "FocalLength": random.choice(self.metadata_options["focal_length"]),
            "WhiteBalance": white_balance_map.get(white_balance_cn, "Auto"),
            "Flash": flash_map.get(flash_cn, "No Flash"),
            "Orientation": random.choice(self.metadata_options["orientation"]),
            
            # Date and Time
            "DateTimeOriginal": date_string,
            "CreateDate": date_string,
            "ModifyDate": date_string,
            
            # GPS
            "GPSLatitude": abs(latitude),
            "GPSLatitudeRef": lat_ref,
            "GPSLongitude": abs(longitude),
            "GPSLongitudeRef": lon_ref,
            "GPSAltitude": altitude,
            "GPSAltitudeRef": random.choice(["Above Sea Level", "Below Sea Level"]),
            "GPSTimeStamp": random_date.strftime("%H:%M:%S"),
            "GPSDateStamp": random_date.strftime("%Y:%m:%d"),
            
            # IPTC/XMP
            "Creator": f"摄影师{random.randint(1, 999)}",
            "Copyright": f"(C){random_date.year} 摄影师, 保留所有权利",  # 使用(C)代替©符号避免编码问题
            "Description": f"使用{make} {model}拍摄的照片",
            "Title": f"IMG_{random.randint(1000, 9999)}"
        }
        
        # 添加关键词和位置信息
        metadata["Keywords"] = ", ".join(random.sample(["自然", "人像", "风景", "城市", "旅行", "人物", "美食", "建筑"], k=random.randint(1, 3)))
        metadata["Location"] = f"地点{random.randint(1, 100)}"
        
        return metadata
    
    def collect_custom_metadata(self):
        metadata = {}
        
        # 中文到英文映射
        white_balance_map = {
            "自动": "Auto", "手动": "Manual", "日光": "Daylight", 
            "阴天": "Cloudy", "钨丝灯": "Tungsten", "荧光灯": "Fluorescent"
        }
        
        flash_map = {
            "无闪光灯": "No Flash", "闪光灯已触发": "Flash Fired", 
            "闪光灯未触发": "Flash Not Fired", "自动闪光灯": "Auto Flash", 
            "红眼减轻": "Red-eye Reduction"
        }
        
        # Helper function to get value based on field type
        def get_field_value(field_name, field_type):
            if field_type == "combobox":
                combo = getattr(self, f"{field_name}_combo")
                value = combo.currentText()
                
                # 处理特殊值
                if value == "【随机生成】":
                    return None  # 将在后面填入随机值
                if value == "【不修改】":
                    return "__NO_CHANGE__"  # 特殊标记表示不修改
                if value == "【空数据】":
                    return "__CLEAR__"  # 特殊标记表示清除数据
                if value == "【自定义...】":
                    return None  # 这不应该发生，返回None表示随机
                
                # 转换中文值到英文
                if field_name == "white_balance" and value in white_balance_map:
                    value = white_balance_map[value]
                elif field_name == "flash" and value in flash_map:
                    value = flash_map[value]
                elif field_name == "gps_latitude_ref":
                    value = "N" if value == "北纬" else "S"
                elif field_name == "gps_longitude_ref":
                    value = "E" if value == "东经" else "W"
                elif field_name == "gps_altitude_ref":
                    value = "Above Sea Level" if value == "海平面以上" else "Below Sea Level"
                    
                return value
            elif field_type == "text":
                type_combo = getattr(self, f"{field_name}_type_combo")
                selection = type_combo.currentText()
                
                # 处理特殊值
                if selection == "【随机生成】":
                    return None  # 将在后面填入随机值
                if selection == "【不修改】":
                    return "__NO_CHANGE__"  # 特殊标记表示不修改
                if selection == "【空数据】":
                    return "__CLEAR__"  # 特殊标记表示清除数据
                
                # 对于自定义输入，获取文本框的值
                if selection == "自定义输入":
                    value = getattr(self, f"{field_name}_text").text()
                    return None if not value else value
                    
                return None  # 默认返回None表示随机
        
        # Camera & Device Information
        metadata["Make"] = get_field_value("make", "combobox")
        metadata["Model"] = get_field_value("model", "combobox")
        metadata["Software"] = get_field_value("software", "combobox")
        metadata["LensModel"] = get_field_value("lens_model", "combobox")
        metadata["ExposureTime"] = get_field_value("exposure_time", "combobox")
        metadata["FNumber"] = get_field_value("fnumber", "combobox")
        metadata["ISO"] = get_field_value("iso", "combobox")
        metadata["FocalLength"] = get_field_value("focal_length", "combobox")
        metadata["WhiteBalance"] = get_field_value("white_balance", "combobox")
        metadata["Flash"] = get_field_value("flash", "combobox")
        metadata["Orientation"] = get_field_value("orientation", "combobox")
        
        # Date and Time Information
        metadata["DateTimeOriginal"] = get_field_value("date_time_original", "text")
        metadata["CreateDate"] = get_field_value("create_date", "text")
        metadata["ModifyDate"] = get_field_value("modify_date", "text")
        
        # GPS Information
        metadata["GPSLatitude"] = get_field_value("gps_latitude", "text")
        metadata["GPSLatitudeRef"] = get_field_value("gps_latitude_ref", "combobox")
        metadata["GPSLongitude"] = get_field_value("gps_longitude", "text")
        metadata["GPSLongitudeRef"] = get_field_value("gps_longitude_ref", "combobox")
        metadata["GPSAltitude"] = get_field_value("gps_altitude", "text")
        metadata["GPSAltitudeRef"] = get_field_value("gps_altitude_ref", "combobox")
        metadata["GPSTimeStamp"] = get_field_value("gps_time_stamp", "text")
        metadata["GPSDateStamp"] = get_field_value("gps_date_stamp", "text")
        
        # IPTC/XMP Information
        metadata["Creator"] = get_field_value("creator", "text")
        metadata["Copyright"] = get_field_value("copyright_notice", "text")
        metadata["Description"] = get_field_value("description", "text")
        metadata["Title"] = get_field_value("title", "text")
        metadata["Keywords"] = get_field_value("keywords", "text")
        metadata["Location"] = get_field_value("location", "text")
        # 删除不存在的字段引用
        # metadata["City"] = get_field_value("city", "text")
        # metadata["State"] = get_field_value("state", "text")
        # metadata["Country"] = get_field_value("country", "combobox")
        
        # 收集所有需要删除的键（不修改的项）
        keys_to_remove = []
        # 处理特殊值
        for key, value in metadata.items():
            if value == "__NO_CHANGE__":
                keys_to_remove.append(key)
                
        # 删除所有不修改的项
        for key in keys_to_remove:
            metadata.pop(key)
        
        # Fill in random values for None fields and handle CLEAR
        random_metadata = self.create_random_metadata()
        for key, value in list(metadata.items()):  # 使用list创建副本进行迭代
            if value is None and key in random_metadata:
                metadata[key] = random_metadata[key]
            elif value == "__CLEAR__":
                # 对应清除数据，设置为空字符串
                metadata[key] = ""
        
        return metadata
    
    def format_metadata_for_preview(self, metadata):
        formatted = []
        
        # 将英文值转换为中文值用于显示
        def get_cn_value(key, en_value):
            # 处理特殊标记
            if en_value == "__NO_CHANGE__":
                return "【不修改】"
            if en_value == "__CLEAR__" or en_value == "":
                return "【清除数据】"
                
            if key == "WhiteBalance" and en_value in self.en_to_cn_mapping["white_balance"]:
                return self.en_to_cn_mapping["white_balance"][en_value]
            elif key == "Flash" and en_value in self.en_to_cn_mapping["flash"]:
                return self.en_to_cn_mapping["flash"][en_value]
            elif key == "GPSLatitudeRef" and en_value in self.en_to_cn_mapping["latitude_ref"]:
                return self.en_to_cn_mapping["latitude_ref"][en_value]
            elif key == "GPSLongitudeRef" and en_value in self.en_to_cn_mapping["longitude_ref"]:
                return self.en_to_cn_mapping["longitude_ref"][en_value]
            elif key == "GPSAltitudeRef" and en_value in self.en_to_cn_mapping["altitude_ref"]:
                return self.en_to_cn_mapping["altitude_ref"][en_value]
            return en_value
        
        # Camera & Device
        formatted.append("===== 相机与设备 =====")
        formatted.append(f"品牌: {metadata.get('Make', '无数据')}")
        formatted.append(f"型号: {metadata.get('Model', '无数据')}")
        formatted.append(f"软件: {metadata.get('Software', '无数据')}")
        formatted.append(f"镜头型号: {metadata.get('LensModel', '无数据')}")
        formatted.append(f"曝光时间: {metadata.get('ExposureTime', '无数据')}")
        formatted.append(f"光圈值: {metadata.get('FNumber', '无数据')}")
        formatted.append(f"ISO: {metadata.get('ISO', '无数据')}")
        formatted.append(f"焦距: {metadata.get('FocalLength', '无数据')}")
        formatted.append(f"白平衡: {get_cn_value('WhiteBalance', metadata.get('WhiteBalance', '无数据'))}")
        formatted.append(f"闪光灯: {get_cn_value('Flash', metadata.get('Flash', '无数据'))}")
        formatted.append(f"方向: {metadata.get('Orientation', '无数据')}")
        
        # Date & Time
        formatted.append("\n===== 日期与时间 =====")
        formatted.append(f"原始拍摄时间: {metadata.get('DateTimeOriginal', '无数据')}")
        formatted.append(f"创建日期: {metadata.get('CreateDate', '无数据')}")
        formatted.append(f"修改日期: {metadata.get('ModifyDate', '无数据')}")
        
        # GPS
        formatted.append("\n===== GPS位置信息 =====")
        formatted.append(f"GPS纬度: {metadata.get('GPSLatitude', '无数据')} {get_cn_value('GPSLatitudeRef', metadata.get('GPSLatitudeRef', '无数据'))}")
        formatted.append(f"GPS经度: {metadata.get('GPSLongitude', '无数据')} {get_cn_value('GPSLongitudeRef', metadata.get('GPSLongitudeRef', '无数据'))}")
        formatted.append(f"GPS海拔: {metadata.get('GPSAltitude', '无数据')} {get_cn_value('GPSAltitudeRef', metadata.get('GPSAltitudeRef', '无数据'))}")
        formatted.append(f"GPS时间戳: {metadata.get('GPSTimeStamp', '无数据')}")
        formatted.append(f"GPS日期戳: {metadata.get('GPSDateStamp', '无数据')}")
        
        # IPTC/XMP
        formatted.append("\n===== 图像描述与版权信息 =====")
        formatted.append(f"创作者: {metadata.get('Creator', '无数据')}")
        formatted.append(f"版权: {metadata.get('Copyright', '无数据')}")
        formatted.append(f"描述: {metadata.get('Description', '无数据')}")
        formatted.append(f"标题: {metadata.get('Title', '无数据')}")
        formatted.append(f"关键词: {metadata.get('Keywords', '无数据')}")
        formatted.append(f"位置: {metadata.get('Location', '无数据')}")
        # 删除不存在的字段引用
        # formatted.append(f"城市: {metadata.get('City', '无数据')}")
        # formatted.append(f"省份/州: {metadata.get('State', '无数据')}")
        # formatted.append(f"国家: {metadata.get('Country', '无数据')}")
        
        return "\n".join(formatted)
    
    def apply_metadata(self, metadata):
        """应用元数据到文件，可以是单个文件或多个文件
        
        参数:
        - metadata: 可以是单个元数据字典，或者是{file_path: metadata}格式的字典
        
        返回:
        - 成功应用元数据的文件数量
        """
        # 检查是否有图片
        if not self.file_paths:
            QMessageBox.warning(self, "警告", "请先添加图片文件")
            return 0
            
        # 检查是否选择了图片（通过复选框）
        checked_files = self.get_checked_files()
        
        # 如果metadata是字典的字典（多个文件），直接使用它
        if isinstance(metadata, dict) and all(isinstance(k, str) and os.path.exists(k) for k in metadata.keys()):
            files_metadata = metadata
        else:
            # 单个元数据字典应用到选中的文件
            if checked_files:
                # 应用到所有被复选框选中的文件
                files_metadata = {file_path: metadata for file_path in checked_files}
            else:
                # 没有选中的文件
                QMessageBox.warning(self, "警告", "请至少选中一个文件进行处理")
                return 0
        
        # 创建进度对话框
        progress_dialog = QProgressDialog("正在应用元数据...", "取消", 0, len(files_metadata), self)
        progress_dialog.setWindowTitle("处理中")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        
        # 应用元数据到每个文件
        success_count = 0
        results = []
        
        try:
            for i, (file_path, file_metadata) in enumerate(files_metadata.items()):
                # 更新进度
                progress_dialog.setValue(i)
                progress_dialog.setLabelText(f"正在处理 ({i+1}/{len(files_metadata)}): {os.path.basename(file_path)}")
                QApplication.processEvents()  # 确保UI更新
                
                # 检查用户是否取消
                if progress_dialog.wasCanceled():
                    break
                    
                success = self._apply_metadata_to_file(file_path, file_metadata)
                if success:
                    success_count += 1
                results.append((file_path, success, file_metadata))
        finally:
            # 确保无论如何进度对话框都会关闭
            progress_dialog.setValue(len(files_metadata))  # 确保进度条到达100%
            progress_dialog.close()
            QApplication.processEvents()  # 立即处理所有待处理的事件，确保对话框关闭
            progress_dialog.deleteLater()  # 安全地销毁对话框
        
        # 显示结果
        if len(results) > 1:  # 多个文件时显示批量结果对话框
            self._show_batch_results(results, "批量应用")
        elif len(results) == 1:  # 单个文件时显示简单消息
            file_path, success, _ = results[0]
            if success:
                QMessageBox.information(self, "成功", f"元数据已成功应用到文件:\n{os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "失败", f"无法应用元数据到文件:\n{os.path.basename(file_path)}")
                
        return success_count
    
    def _apply_metadata_to_file(self, file_path, metadata):
        """应用元数据到单个文件，返回操作是否成功"""
        if not self.exiftool_path or not os.path.exists(self.exiftool_path):
            QMessageBox.critical(self, "错误", "ExifTool路径未设置或无效，无法修改元数据")
            return False
            
        if not file_path or not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return False
            
        # 创建临时文件名
        temp_file = file_path + "_temp"
        
        # 拼接ExifTool命令
        command = []
        for key, value in metadata.items():
            # 处理特殊情况：空值或清除标记
            if value == "__CLEAR__" or value == "":
                command.append(f"-{key}=")  # 用空值覆盖
            # 处理不修改标记
            elif value == "__NO_CHANGE__":
                continue  # 跳过此字段
            else:
                # 正常值
                command.append(f"-{key}={value}")
        
        if not command:
            # 没有任何修改
            return True
            
        try:
            # 使用with语句确保进程关闭
            with exiftool.ExifToolHelper(executable=self.exiftool_path) as et:
                # 对单个文件应用所有元数据修改
                et.execute("-overwrite_original", *command, file_path)
                print(f"元数据已成功应用到: {file_path}")
                return True
        except Exception as e:
            print(f"应用元数据时出错: {e}")
            return False
    
    def save_settings(self):
        # 保存ExifTool路径
        self.settings.setValue("exiftool_path", self.exiftool_path)
        
        # 保存所有自定义字段设置
        settings = {}
        
        # Helper to save a field's state
        def save_field_state(field_name, field_type):
            if field_type == "combobox":
                combo = getattr(self, f"{field_name}_combo")
                settings[f"{field_name}_random"] = (combo.currentText() == "【随机生成】")
                settings[f"{field_name}_value"] = combo.currentText()
            elif field_type == "text":
                type_combo = getattr(self, f"{field_name}_type_combo")
                text = getattr(self, f"{field_name}_text")
                settings[f"{field_name}_random"] = (type_combo.currentText() == "【随机生成】")
                settings[f"{field_name}_value"] = text.text()
        
        # Camera & Device Information
        save_field_state("make", "combobox")
        save_field_state("model", "combobox")
        save_field_state("software", "combobox")
        save_field_state("lens_model", "combobox")
        save_field_state("exposure_time", "combobox")
        save_field_state("fnumber", "combobox")
        save_field_state("iso", "combobox")
        save_field_state("focal_length", "combobox")
        save_field_state("white_balance", "combobox")
        save_field_state("flash", "combobox")
        save_field_state("orientation", "combobox")
        
        # Date and Time Information
        save_field_state("date_time_original", "text")
        save_field_state("create_date", "text")
        save_field_state("modify_date", "text")
        
        # GPS Information
        save_field_state("gps_latitude", "text")
        save_field_state("gps_latitude_ref", "combobox")
        save_field_state("gps_longitude", "text")
        save_field_state("gps_longitude_ref", "combobox")
        save_field_state("gps_altitude", "text")
        save_field_state("gps_altitude_ref", "combobox")
        save_field_state("gps_time_stamp", "text")
        save_field_state("gps_date_stamp", "text")
        
        # IPTC/XMP Information
        save_field_state("creator", "text")
        save_field_state("copyright_notice", "text")
        save_field_state("description", "text")
        save_field_state("title", "text")
        save_field_state("keywords", "text")
        save_field_state("location", "text")
        save_field_state("city", "text")
        save_field_state("state", "text")
        save_field_state("country", "combobox")
        
        # Save settings to QSettings
        self.settings.setValue("custom_settings", json.dumps(settings))
        
        QMessageBox.information(self, "设置已保存", "您的自定义设置已保存为默认值。")
    
    def load_settings(self):
        """加载软件设置"""
        # 加载ExifTool路径
        self.exiftool_path = self.settings.value("exiftool_path", "")
        
        try:
            # 自定义模式下的设置
            custom_fields = [
                ("make", "combobox"), ("model", "combobox"), ("software", "combobox"), ("lens_model", "combobox"),
                ("exposure_time", "combobox"), ("fnumber", "combobox"), ("iso", "combobox"), ("focal_length", "combobox"),
                ("white_balance", "combobox"), ("flash", "combobox"), ("orientation", "combobox"),
                ("date_time_original", "text"), ("create_date", "text"), ("modify_date", "text"),
                ("gps_latitude", "text"), ("gps_latitude_ref", "combobox"), 
                ("gps_longitude", "text"), ("gps_longitude_ref", "combobox"),
                ("gps_altitude", "text"), ("gps_altitude_ref", "combobox"),
                ("gps_time_stamp", "text"), ("gps_date_stamp", "text"),
                ("creator", "text"), ("copyright_notice", "text"), ("description", "text"), 
                ("title", "text"), ("keywords", "text"), ("location", "text")
            ]
            
            def load_field_state(field_name, field_type):
                try:
                    # 跳过未实现的字段以避免错误
                    if not (hasattr(self, f"{field_name}_combo") or hasattr(self, f"{field_name}_type_combo")):
                        return
                        
                    # 恢复下拉框状态
                    if field_type == "combobox":
                        combo = getattr(self, f"{field_name}_combo")
                        saved_index = self.settings.value(f"custom/{field_name}/index", 0, type=int)
                        saved_text = self.settings.value(f"custom/{field_name}/text", "")
                        
                        # 首先尝试通过文本找到项
                        if saved_text:
                            index = combo.findText(saved_text)
                            if index >= 0:
                                combo.setCurrentIndex(index)
                                return
                        
                        # 如果找不到匹配的文本，使用保存的索引
                        if 0 <= saved_index < combo.count():
                            combo.setCurrentIndex(saved_index)
                    
                    # 恢复文本字段状态    
                    elif field_type == "text":
                        if hasattr(self, f"{field_name}_type_combo"):
                            type_combo = getattr(self, f"{field_name}_type_combo")
                            saved_index = self.settings.value(f"custom/{field_name}/index", 0, type=int)
                            if 0 <= saved_index < type_combo.count():
                                type_combo.setCurrentIndex(saved_index)
                            
                            if saved_index == 3:  # 自定义输入
                                if hasattr(self, f"{field_name}_text"):
                                    text = getattr(self, f"{field_name}_text")
                                    saved_text = self.settings.value(f"custom/{field_name}/text", "")
                                    text.setText(saved_text)
                except Exception as e:
                    print(f"加载{field_name}设置时出错: {str(e)}")
            
            # 加载每个字段的状态
            for field_name, field_type in custom_fields:
                load_field_state(field_name, field_type)
                
        except Exception as e:
            print(f"加载设置时出错: {str(e)}")
    
    def browse_exiftool(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择ExifTool可执行文件", "", "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if path and os.path.exists(path):
            self.exiftool_path = path
            self.exiftool_path_edit.setText(self.exiftool_path)
            # 保存新的ExifTool路径
            self.settings.setValue("exiftool_path", self.exiftool_path)

    def handle_no_change(self, field_name):
        """处理'不修改'按钮点击事件"""
        # 设置为自定义模式并输入特殊标记值
        if hasattr(self, f"{field_name}_check"):
            getattr(self, f"{field_name}_check").setChecked(False)  # 不使用随机
            
            if hasattr(self, f"{field_name}_combo"):
                stack = getattr(self, f"{field_name}_stack")
                combo = getattr(self, f"{field_name}_combo")
                stack.setCurrentIndex(0)  # 确保显示下拉菜单
                
                # 添加一个"不修改"项，如果还没有的话
                if combo.findText("【不修改】") == -1:
                    combo.insertItem(2, "【不修改】")  # 插入到自定义选项后面
                combo.setCurrentText("【不修改】")
            elif hasattr(self, f"{field_name}_text"):
                text = getattr(self, f"{field_name}_text")
                text.setEnabled(True)
                text.setText("【不修改】")
    
    def handle_clear_data(self, field_name):
        """处理'清除数据'按钮点击事件"""
        # 设置为自定义模式并输入特殊标记值
        if hasattr(self, f"{field_name}_check"):
            getattr(self, f"{field_name}_check").setChecked(False)  # 不使用随机
            
            if hasattr(self, f"{field_name}_combo"):
                stack = getattr(self, f"{field_name}_stack")
                combo = getattr(self, f"{field_name}_combo")
                stack.setCurrentIndex(0)  # 确保显示下拉菜单
                
                # 添加一个"清除数据"项，如果还没有的话
                if combo.findText("【清除数据】") == -1:
                    combo.insertItem(2, "【清除数据】")  # 插入到自定义选项后面
                combo.setCurrentText("【清除数据】")
            elif hasattr(self, f"{field_name}_text"):
                text = getattr(self, f"{field_name}_text")
                text.setEnabled(True)
                text.setText("【清除数据】")

    def delete_custom_item(self, field_name, index):
        """删除自定义选项"""
        combo = getattr(self, f"{field_name}_combo")
        text = combo.itemText(index)
        
        # 确认删除
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定要删除自定义选项 \"{text}\" 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 记住当前选择的文本
            current_text = combo.currentText()
            
            # 移除项
            combo.removeItem(index)
            
            # 如果删除的就是当前选择的项，则选择"随机生成"
            if text == current_text:
                combo.setCurrentIndex(0)
            else:
                # 否则尝试重新选择之前选择的项
                new_index = combo.findText(current_text)
                if new_index >= 0:
                    combo.setCurrentIndex(new_index)
                else:
                    combo.setCurrentIndex(0)
    
    def add_custom_item(self, field_name):
        """添加自定义选项"""
        # 切换到自定义文本输入界面
        stack = getattr(self, f"{field_name}_stack")
        stack.setCurrentIndex(1)  # 切换到文本输入界面
        
        # 设置焦点到文本输入框
        custom_text = getattr(self, f"{field_name}_custom_text")
        custom_text.clear()
        custom_text.setFocus()
    
    def clear_custom_items(self, field_name, show_confirmation=True):
        """清除所有自定义选项"""
        combo = getattr(self, f"{field_name}_combo")
        
        # 确认删除
        should_proceed = True
        if show_confirmation:
            reply = QMessageBox.question(
                self, 
                "确认清除", 
                "确定要清除所有自定义选项吗？\n\n预设选项将保留。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            should_proceed = (reply == QMessageBox.Yes)
        
        if should_proceed:
            # 保留的预定义选项
            preserved_items = ["【随机生成】", "【不修改】", "【空数据】", "【自定义...】"]
            
            # 移除非预定义项
            i = 0
            while i < combo.count():
                text = combo.itemText(i)
                if text not in preserved_items and i >= 4:  # 跳过前四个固定选项
                    combo.removeItem(i)
                else:
                    i += 1
            
            # 选择"随机生成"选项
            combo.setCurrentIndex(0)
    
    def apply_common_value(self, field_name, value):
        """应用常用值"""
        combo = getattr(self, f"{field_name}_combo")
        
        # 检查是否已存在此值
        index = combo.findText(value)
        if index > 0:
            combo.setCurrentIndex(index)
        else:
            # 如果不存在，添加到第五个位置（在所有特殊选项之后）
            combo.insertItem(4, value)
            combo.setCurrentIndex(4)
            
    def confirm_custom_value(self, field_name):
        """确认自定义值，返回到下拉菜单界面"""
        custom_text = getattr(self, f"{field_name}_custom_text")
        custom_value = custom_text.text().strip()
        
        if not custom_value:
            QMessageBox.warning(self, "输入错误", "请输入有效的自定义值，或点击取消返回。")
            custom_text.setFocus()
            return
        
        combo = getattr(self, f"{field_name}_combo")
        
        # 检查是否已存在此自定义值
        found = False
        for i in range(combo.count()):
            if combo.itemText(i) == custom_value:
                found = True
                combo.setCurrentIndex(i)
                break
        
        # 如果不存在，添加到第五个位置（在所有特殊选项之后）
        if not found:
            combo.insertItem(4, custom_value)
            combo.setCurrentIndex(4)
        
        # 切换回下拉菜单界面
        stack = getattr(self, f"{field_name}_stack")
        stack.setCurrentIndex(0)
    
    def cancel_custom_value(self, field_name):
        """取消自定义输入，返回到下拉菜单界面"""
        combo = getattr(self, f"{field_name}_combo")
        
        # 如果之前选中的是"【自定义...】"，则还原到第一个选项"【随机生成】"
        if combo.currentText() == "【自定义...】":
            combo.setCurrentIndex(0)
        
        # 切换回下拉菜单界面
        stack = getattr(self, f"{field_name}_stack")
        stack.setCurrentIndex(0)
    
    def reset_settings(self):
        """重置所有设置为默认状态"""
        # 确认重置
        reply = QMessageBox.question(
            self, 
            "确认重置", 
            "确定要重置所有设置为初始状态吗？所有保存的自定义选项将被删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 重置ExifTool路径
        settings = QSettings("ImageMetadataEditor", "Settings")
        settings.remove("exiftool_path")  # 删除保存的路径
        
        # 重置所有选择框为第一项（随机生成）
        combo_fields = ["make", "model", "software", "lens_model", 
                      "exposure_time", "fnumber", "iso", "focal_length", 
                      "white_balance", "flash", "orientation",
                      "gps_latitude_ref", "gps_longitude_ref", "gps_altitude_ref"]
                      
        for field_name in combo_fields:
            combo = getattr(self, f"{field_name}_combo", None)
            if combo:
                combo.setCurrentIndex(0)  # 设置为第一项
        
        # 重置所有文本类型选择框为随机生成
        text_fields = ["date_time_original", "create_date", "modify_date", 
                      "gps_latitude", "gps_longitude", "gps_altitude", 
                      "gps_time_stamp", "gps_date_stamp", 
                      "creator", "copyright_notice", "description", 
                      "title", "keywords", "location"]
                      
        for field_name in text_fields:
            type_combo = getattr(self, f"{field_name}_type_combo", None)
            if type_combo:
                type_combo.setCurrentIndex(0)  # 设置为随机生成
                
            # 清空文本框
            text_field = getattr(self, f"{field_name}_text", None)
            if text_field:
                text_field.clear()
        
        # 清除所有自定义选项，禁用确认对话框
        for field_name in combo_fields:
            if hasattr(self, f"{field_name}_combo"):
                self.clear_custom_items(field_name, show_confirmation=False)
        
        QMessageBox.information(self, "重置完成", "所有设置已恢复为默认值。")

    def _show_batch_preview(self, all_metadata, mode_name):
        """显示批量处理预览"""
        # 创建预览对话框
        preview_dialog = QMessageBox()
        preview_dialog.setWindowTitle(f"批量{mode_name}元数据预览")
        preview_dialog.setText(f"将为 {len(all_metadata)} 个文件应用{mode_name}元数据。")
        
        # 创建详细文本
        preview_text = "每个文件的元数据详情：\n\n"
        for file_path, metadata in all_metadata.items():
            file_name = os.path.basename(file_path)
            preview_text += f"=== {file_name} ===\n"
            preview_text += self.format_metadata_for_preview(metadata)
            preview_text += "\n\n" + "-"*40 + "\n\n"
        
        preview_dialog.setDetailedText(preview_text)
        
        # 设置更大的尺寸
        preview_dialog.setMinimumWidth(700)
        
        # 自定义按钮
        apply_button = preview_dialog.addButton(f"应用到所有文件", QMessageBox.ApplyRole)
        cancel_button = preview_dialog.addButton("取消", QMessageBox.RejectRole)
        preview_dialog.setDefaultButton(apply_button)
        
        # 修改系统生成的"Show Details..."按钮文本
        for button in preview_dialog.buttons():
            if preview_dialog.buttonRole(button) == QMessageBox.ActionRole:
                button.setText("查看详情...")
        
        # 显示对话框
        result = preview_dialog.exec_()
        
        # 手动设置文本编辑区域的大小
        detail_text_edit = preview_dialog.findChild(QTextEdit)
        if detail_text_edit:
            detail_text_edit.setMinimumSize(600, 500)
        
        if preview_dialog.clickedButton() == apply_button:
            # 处理每个文件
            self._apply_batch_metadata(all_metadata)
            
    def _apply_batch_metadata(self, all_metadata):
        """批量应用元数据到多个文件"""
        # 直接调用apply_metadata处理批量元数据
        self.apply_metadata(all_metadata)
    
    def slightly_vary_metadata(self, base_metadata, file_path):
        """为每个文件稍微变化随机元数据以增加真实性"""
        # 创建一个基础元数据的副本，以免修改原始数据
        varied_metadata = base_metadata.copy()
        
        # 获取文件名，用作随机种子的一部分，确保同一文件总是获得相同的随机变化
        file_name = os.path.basename(file_path)
        # 创建一个基于文件名的随机种子
        seed = hash(file_name) % 10000
        random.seed(seed)
        
        # 大幅调整日期时间（近一年范围内的随机值）
        for date_field in ["DateTimeOriginal", "CreateDate", "ModifyDate"]:
            if date_field in varied_metadata and varied_metadata[date_field]:
                try:
                    # 解析日期时间字符串
                    dt = datetime.datetime.strptime(varied_metadata[date_field], "%Y:%m:%d %H:%M:%S")
                    
                    # 近一年范围内的随机值（-6个月到+6个月）
                    delta_days = random.randint(-180, 180)  # ±180天（约6个月）
                    delta_hours = random.randint(-23, 23)   # 随机小时
                    delta_minutes = random.randint(-59, 59) # 随机分钟
                    delta_seconds = random.randint(0, 59)   # 随机秒
                    
                    dt = dt + datetime.timedelta(days=delta_days, 
                                                hours=delta_hours, 
                                                minutes=delta_minutes, 
                                                seconds=delta_seconds)
                    
                    # 更新元数据
                    varied_metadata[date_field] = dt.strftime("%Y:%m:%d %H:%M:%S")
                except (ValueError, TypeError):
                    # 如果日期格式不正确，保持原样
                    pass
        
        # 大幅调整GPS坐标 (±9度，大约相当于1000公里)
        for coord_field in ["GPSLatitude", "GPSLongitude"]:
            if coord_field in varied_metadata and varied_metadata[coord_field] is not None:
                try:
                    coord = float(varied_metadata[coord_field])
                    # 1度约等于111公里，所以1000公里约为9度
                    delta = random.uniform(-9.0, 9.0)
                    
                    # 对于纬度，确保在-90到90之间
                    if coord_field == "GPSLatitude":
                        new_coord = max(-90, min(90, coord + delta))
                    # 对于经度，确保在-180到180之间，或处理环绕情况
                    else:
                        new_coord = (coord + delta) % 360
                        if new_coord > 180:
                            new_coord -= 360
                    
                    varied_metadata[coord_field] = new_coord
                    
                    # 如果坐标符号改变，需要更新参考方向
                    if coord_field == "GPSLatitude" and "GPSLatitudeRef" in varied_metadata:
                        varied_metadata["GPSLatitudeRef"] = "N" if new_coord >= 0 else "S"
                    if coord_field == "GPSLongitude" and "GPSLongitudeRef" in varied_metadata:
                        varied_metadata["GPSLongitudeRef"] = "E" if new_coord >= 0 else "W"
                        
                except (ValueError, TypeError):
                    # 如果坐标不是有效数字，保持原样
                    pass
        
        # 微调高度 (±2000米)
        if "GPSAltitude" in varied_metadata and varied_metadata["GPSAltitude"] is not None:
            try:
                altitude = float(varied_metadata["GPSAltitude"])
                delta = random.uniform(-2000, 2000)
                varied_metadata["GPSAltitude"] = max(0, altitude + delta)  # 确保高度不为负
            except (ValueError, TypeError):
                pass
        
        # 微调曝光时间 (±30%)
        if "ExposureTime" in varied_metadata and varied_metadata["ExposureTime"]:
            try:
                # 曝光时间通常是分数形式，如"1/100"
                exposure = varied_metadata["ExposureTime"]
                if "/" in exposure:
                    num, denom = exposure.split("/")
                    num, denom = float(num), float(denom)
                    value = num / denom
                    # 在原值基础上上下浮动30%
                    factor = random.uniform(0.7, 1.3)
                    new_value = value * factor
                    
                    # 转回分数形式
                    if new_value < 1:
                        new_denom = int(1 / new_value)
                        varied_metadata["ExposureTime"] = f"1/{new_denom}"
                    else:
                        varied_metadata["ExposureTime"] = str(round(new_value, 2))
            except (ValueError, TypeError, ZeroDivisionError):
                pass
        
        # 微调光圈值 (±1档)
        if "FNumber" in varied_metadata and varied_metadata["FNumber"]:
            try:
                fnumber = float(varied_metadata["FNumber"])
                # 光圈F值通常按照sqrt(2)的倍数变化（即1档）
                stops = random.uniform(-1, 1)  # ±1档
                new_fnumber = fnumber * (2 ** (stops/2))
                varied_metadata["FNumber"] = str(round(new_fnumber, 1))
            except (ValueError, TypeError):
                pass
        
        # 微调ISO值 (±100)
        if "ISO" in varied_metadata and varied_metadata["ISO"]:
            try:
                iso = int(varied_metadata["ISO"])
                delta = random.randint(-100, 100)
                new_iso = max(100, iso + delta)  # 确保ISO不低于100
                varied_metadata["ISO"] = str(new_iso)
            except (ValueError, TypeError):
                pass
        
        # 微调焦距 (±20%)
        if "FocalLength" in varied_metadata and varied_metadata["FocalLength"]:
            try:
                focal_str = varied_metadata["FocalLength"]
                if "mm" in focal_str:
                    focal = float(focal_str.replace("mm", "").strip())
                    # 上下浮动20%
                    delta_percent = random.uniform(-0.2, 0.2)
                    new_focal = focal * (1 + delta_percent)
                    varied_metadata["FocalLength"] = f"{int(new_focal)} mm"
            except (ValueError, TypeError):
                pass
        
        # 随机切换白平衡或闪光灯设置
        if "WhiteBalance" in varied_metadata and random.random() < 0.3:  # 30%的概率改变白平衡
            white_balance_options = ["Auto", "Manual", "Daylight", "Cloudy", "Tungsten", "Fluorescent"]
            varied_metadata["WhiteBalance"] = random.choice(white_balance_options)
            
        if "Flash" in varied_metadata and random.random() < 0.3:  # 30%的概率改变闪光灯设置
            flash_options = ["No Flash", "Flash Fired", "Flash Not Fired", "Auto Flash", "Red-eye Reduction"]
            varied_metadata["Flash"] = random.choice(flash_options)
        
        # 重置随机种子，避免影响程序其他部分
        random.seed()
        
        return varied_metadata

    # 拖放事件处理
    def dragEnterEvent(self, event):
        """拖动进入事件"""
        # 检查是否包含文件
        if event.mimeData().hasUrls():
            # 只接受文件URL
            event.acceptProposedAction()

    def dropEvent(self, event):
        """放下事件"""
        # 获取拖放的文件URL
        urls = event.mimeData().urls()
        
        # 提取文件路径
        file_paths = []
        for url in urls:
            file_path = url.toLocalFile()
            
            # 检查是否是支持的图片格式
            _, ext = os.path.splitext(file_path)
            if ext.lower() in ['.jpg', '.jpeg', '.png', '.tiff', '.heic', '.webp', '.bmp']:
                file_paths.append(file_path)
        
        # 添加文件
        if file_paths:
            self.add_files(file_paths)
            
        event.acceptProposedAction()

    # 添加保存为默认设置和重置为默认设置的方法
    def save_as_default_settings(self):
        """保存当前所有设置为模板"""
        try:
            # 获取当前所有字段的设置
            default_settings = {}
            
            # 遍历所有组合框控件
            combo_fields = ["make", "model", "software", "lens_model", 
                          "exposure_time", "fnumber", "iso", "focal_length", 
                          "white_balance", "flash", "orientation",
                          "gps_latitude_ref", "gps_longitude_ref", "gps_altitude_ref",
                          "country"]  # 添加country字段
            
            for field in combo_fields:
                combo = getattr(self, f"{field}_combo", None)
                if combo:
                    default_settings[f"{field}_combo"] = combo.currentText()
            
            # 遍历所有文本框控件
            text_fields = ["date_time_original", "create_date", "modify_date", 
                          "gps_latitude", "gps_longitude", "gps_altitude", 
                          "gps_time_stamp", "gps_date_stamp", 
                          "creator", "copyright_notice", "description", 
                          "title", "keywords", "location", "city", "state"]  # 添加city和state字段
            
            for field in text_fields:
                # 保存类型选择
                type_combo = getattr(self, f"{field}_type_combo", None)
                if type_combo:
                    default_settings[f"{field}_type_combo"] = type_combo.currentText()
                
                # 如果是自定义输入，保存文本值
                text_field = getattr(self, f"{field}_text", None)
                if text_field:
                    default_settings[f"{field}_text"] = text_field.text()
            
            # 保存到QSettings - 模板设置
            template_settings = QSettings("ImageMetadataEditor", "TemplateSettings")
            template_settings.setValue("template_settings", default_settings)
            
            # 同时保存为当前会话设置，以便下次启动时自动加载
            session_settings = QSettings("ImageMetadataEditor", "SessionSettings")
            session_settings.setValue("current_settings", default_settings)
            session_settings.sync()  # 确保设置被写入到存储
            
            print("设置已保存: ", len(default_settings), "项")
            QMessageBox.information(self, "保存成功", "当前设置已成功保存为模板，并将在下次启动时自动加载")
        except Exception as e:
            print(f"保存设置时出错: {str(e)}")
            QMessageBox.warning(self, "保存失败", f"保存设置时出错: {str(e)}")

    def reset_to_default_settings(self):
        """从保存的模板中恢复设置"""
        try:
            # 从QSettings加载模板设置
            settings = QSettings("ImageMetadataEditor", "TemplateSettings")
            template_settings = settings.value("template_settings")
            
            if not template_settings:
                QMessageBox.warning(self, "提示", "未找到保存的设置模板，请先保存一次设置模板")
                return
            
            # 确认对话框
            reply = QMessageBox.question(
                self, 
                "确认操作", 
                "确定要加载保存的设置模板吗？当前未保存的设置将丢失。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 恢复所有控件的值
            for key, value in template_settings.items():
                control = getattr(self, key, None)
                if control:
                    if isinstance(control, QComboBox):
                        index = control.findText(value)
                        if index >= 0:
                            control.setCurrentIndex(index)
                    elif isinstance(control, QLineEdit):
                        control.setText(value)
            
            QMessageBox.information(self, "加载完成", "已从保存的模板中恢复设置")
        except Exception as e:
            print(f"加载模板设置时出错: {str(e)}")
            QMessageBox.warning(self, "加载失败", f"加载模板设置时出错: {str(e)}")

    def load_last_session_settings(self):
        """加载上次退出时的设置"""
        try:
            # 使用更可靠的方式加载配置
            session_settings = QSettings("ImageMetadataEditor", "SessionSettings")
            template_settings = session_settings.value("current_settings")
            
            if not template_settings:
                print("未找到上次会话的设置，使用默认值")
                return  # 没有保存的设置，使用默认值
            
            # 暂存需要特殊处理的值
            lens_model_value = template_settings.get("lens_model_combo", None)
            
            # 恢复所有控件的值
            for key, value in template_settings.items():
                try:
                    control = getattr(self, key, None)
                    if control:
                        if isinstance(control, QComboBox):
                            index = control.findText(value)
                            if index >= 0:
                                control.setCurrentIndex(index)
                        elif isinstance(control, QLineEdit):
                            control.setText(value)
                except Exception as e:
                    print(f"加载设置'{key}'时出错: {str(e)}")
                    continue  # 继续加载其他设置
            
            # 在所有设置加载后，手动处理lens_model_combo
            # 这确保镜头型号的值不会被make_combo.currentIndexChanged信号的处理覆盖
            if lens_model_value and lens_model_value == "【空数据】":
                try:
                    # 延迟处理镜头型号设置，确保其他UI元素都已加载
                    QApplication.processEvents()
                    # 确保lens_model_combo正确设置为空数据
                    index = self.lens_model_combo.findText("【空数据】")
                    if index >= 0:
                        self.lens_model_combo.setCurrentIndex(index)
                        print("成功恢复镜头型号为【空数据】")
                except Exception as e:
                    print(f"恢复镜头型号时出错: {str(e)}")
                    
            print("成功加载上次会话设置")
        except Exception as e:
            print(f"加载会话设置时出错: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ImageMetadataEditor()
    editor.show()
    sys.exit(app.exec_())
