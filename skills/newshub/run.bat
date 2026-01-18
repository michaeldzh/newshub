@echo off
REM Global News Aggregator - Windows Convenience Script
REM Usage: run.bat [command]

setlocal

if "%1"=="" (
    echo Global News Aggregator - Available Commands:
    echo.
    echo   run.bat setup          - Run interactive setup
    echo   run.bat test           - Run test suite
    echo   run.bat demo           - Run demo with sample data
    echo   run.bat generate       - Generate news report
    echo   run.bat install-deps   - Install Python dependencies
    echo   run.bat help           - Show this help message
    echo.
    goto :eof
)

if "%1"=="setup" (
    echo Running setup...
    python setup.py
    goto :eof
)

if "%1"=="test" (
    echo Running tests...
    python test_skill.py
    goto :eof
)

if "%1"=="demo" (
    echo Running demo...
    python demo.py
    if exist demo_news_report.html (
        echo.
        echo Demo report generated: demo_news_report.html
        echo Opening in browser...
        start demo_news_report.html
    )
    goto :eof
)

if "%1"=="generate" (
    if not exist api-config.json (
        echo Error: api-config.json not found
        echo Please run: run.bat setup
        exit /b 1
    )
    echo Generating news report...
    python enhanced_news_aggregator.py api-config.json
    if exist global_news_report.html (
        echo.
        echo Report generated: global_news_report.html
        set /p OPEN="Open in browser? (y/n): "
        if /i "%OPEN%"=="y" start global_news_report.html
    )
    goto :eof
)

if "%1"=="install-deps" (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
    goto :eof
)

if "%1"=="help" (
    echo Global News Aggregator Skill
    echo.
    echo This skill aggregates news from multiple sources and generates HTML reports.
    echo.
    echo Quick Start:
    echo   1. run.bat install-deps
    echo   2. run.bat setup
    echo   3. run.bat generate
    echo.
    echo For more information, see README.md or QUICKSTART.md
    goto :eof
)

echo Unknown command: %1
echo Run 'run.bat' without arguments to see available commands.
exit /b 1
