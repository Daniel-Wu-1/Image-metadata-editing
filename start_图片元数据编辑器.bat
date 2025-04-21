@echo off
chcp 65001 >nul
color 0A
title 图片元数据编辑器启动器
cls

echo ================================================
echo             图片元数据编辑器启动器
echo ================================================
echo.

:: 检查Python是否安装
echo [1/4] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo 错误: 未检测到Python，请确保已安装Python 3.6或更高版本。
    echo 您可以从 https://www.python.org/downloads/ 下载Python。
    echo.
    pause
    exit /b
)

:: 获取当前目录
set CURRENT_DIR=%~dp0

:: 检查需要的依赖
echo [2/4] 检查依赖项...
set DEPENDENCIES_OK=1

python -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    set DEPENDENCIES_OK=0
    echo     - 正在安装PyQt5...
    pip install PyQt5==5.15.9
    if %errorlevel% neq 0 (
        color 0C
        echo 错误: PyQt5安装失败
        pause
        exit /b
    )
)

python -c "import exiftool" >nul 2>&1
if %errorlevel% neq 0 (
    set DEPENDENCIES_OK=0
    echo     - 正在安装pyexiftool...
    pip install pyexiftool==0.5.5
    if %errorlevel% neq 0 (
        color 0C
        echo 错误: pyexiftool安装失败
        pause
        exit /b
    )
)

python -c "from PIL import Image" >nul 2>&1
if %errorlevel% neq 0 (
    set DEPENDENCIES_OK=0
    echo     - 正在安装Pillow图像处理库...
    pip install pillow==10.0.0
    if %errorlevel% neq 0 (
        color 0C
        echo 警告: Pillow安装失败，某些图片格式可能无法正常显示
        echo 但程序仍可继续使用
        timeout /t 5 >nul
    )
)

if %DEPENDENCIES_OK%==1 (
    echo     - 所有依赖已安装
)

:: 检查ExifTool路径
echo [3/4] 检查ExifTool...
set EXIFTOOL_FOUND=0

:: 检查当前目录下是否有ExifTool
if exist "%CURRENT_DIR%exiftool.exe" (
    set EXIFTOOL_FOUND=1
    echo     - 在当前目录找到ExifTool
)

:: 检查exiftool子目录
if %EXIFTOOL_FOUND%==0 (
    if exist "%CURRENT_DIR%exiftool\exiftool.exe" (
        set EXIFTOOL_FOUND=1
        echo     - 在exiftool子目录找到ExifTool
    )
)

:: 检查可能的ExifTool安装目录
if %EXIFTOOL_FOUND%==0 (
    for %%G in (
        "%CURRENT_DIR%exiftool-*\exiftool.exe"
    ) do (
        if exist "%%G" (
            set EXIFTOOL_FOUND=1
            echo     - 找到ExifTool: %%G
        )
    )
)

if %EXIFTOOL_FOUND%==0 (
    echo     - 警告: 未找到ExifTool
    echo       您可以从 https://exiftool.org/ 下载ExifTool
    echo       解压后将exiftool.exe放在程序目录或子目录中
    echo       或者在程序启动后手动设置ExifTool路径
    echo.
)

:: 准备启动
echo [4/4] 准备启动程序...
echo     - 当前版本：1.0.0
echo.
echo 所有检查完毕，准备启动程序...
echo ================================================
echo.
timeout /t 2 >nul

:: 启动程序
echo 正在启动图片元数据编辑器...
python "%CURRENT_DIR%1.py"

:: 如果程序异常退出，保持窗口不关闭
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo 程序异常退出，错误代码: %errorlevel%
    echo.
    pause
) 