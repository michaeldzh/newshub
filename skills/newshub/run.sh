#!/bin/bash
# Global News Aggregator - Unix/Linux/Mac Convenience Script
# Usage: ./run.sh [command]

set -e

show_help() {
    echo "Global News Aggregator - Available Commands:"
    echo ""
    echo "  ./run.sh setup          - Run interactive setup"
    echo "  ./run.sh test           - Run test suite"
    echo "  ./run.sh demo           - Run demo with sample data"
    echo "  ./run.sh generate       - Generate news report"
    echo "  ./run.sh install-deps   - Install Python dependencies"
    echo "  ./run.sh help           - Show this help message"
    echo ""
}

if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

case "$1" in
    setup)
        echo "Running setup..."
        python3 setup.py
        ;;

    test)
        echo "Running tests..."
        python3 test_skill.py
        ;;

    demo)
        echo "Running demo..."
        python3 demo.py
        if [ -f "demo_news_report.html" ]; then
            echo ""
            echo "Demo report generated: demo_news_report.html"
            echo "Opening in browser..."
            if command -v xdg-open > /dev/null; then
                xdg-open demo_news_report.html
            elif command -v open > /dev/null; then
                open demo_news_report.html
            else
                echo "Please open demo_news_report.html manually"
            fi
        fi
        ;;

    generate)
        if [ ! -f "api-config.json" ]; then
            echo "Error: api-config.json not found"
            echo "Please run: ./run.sh setup"
            exit 1
        fi
        echo "Generating news report..."
        python3 enhanced_news_aggregator.py api-config.json
        if [ -f "global_news_report.html" ]; then
            echo ""
            echo "Report generated: global_news_report.html"
            read -p "Open in browser? (y/n): " OPEN
            if [ "$OPEN" = "y" ] || [ "$OPEN" = "Y" ]; then
                if command -v xdg-open > /dev/null; then
                    xdg-open global_news_report.html
                elif command -v open > /dev/null; then
                    open global_news_report.html
                else
                    echo "Please open global_news_report.html manually"
                fi
            fi
        fi
        ;;

    install-deps)
        echo "Installing dependencies..."
        python3 -m pip install -r requirements.txt
        ;;

    help)
        echo "Global News Aggregator Skill"
        echo ""
        echo "This skill aggregates news from multiple sources and generates HTML reports."
        echo ""
        echo "Quick Start:"
        echo "  1. ./run.sh install-deps"
        echo "  2. ./run.sh setup"
        echo "  3. ./run.sh generate"
        echo ""
        echo "For more information, see README.md or QUICKSTART.md"
        ;;

    *)
        echo "Unknown command: $1"
        echo "Run './run.sh' without arguments to see available commands."
        exit 1
        ;;
esac
