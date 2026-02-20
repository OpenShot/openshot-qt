#!/bin/bash

SERVICE_DIR="/home/lol/project/core/remotion-service"
PID_FILE="$SERVICE_DIR/remotion.pid"

start() {
    echo "Starting Remotion service..."
    cd "$SERVICE_DIR"
    nohup npm run serve > remotion.log 2>&1 &
    echo $! > "$PID_FILE"
    echo "Remotion service started (PID: $(cat $PID_FILE))"
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        echo "Stopping Remotion service (PID: $PID)..."
        kill $PID 2>/dev/null
        rm "$PID_FILE"
        echo "Remotion service stopped"
    else
        echo "Remotion service is not running"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Remotion service is running (PID: $PID)"
        else
            echo "PID file exists but process is not running"
            rm "$PID_FILE"
        fi
    else
        echo "Remotion service is not running"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
esac
