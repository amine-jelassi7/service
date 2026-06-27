package main

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sync"
	"time"
)

type Worker struct {
	id     int
	cmd    *exec.Cmd
	conn   net.Conn
	socket string
	mu     sync.Mutex
}

type WorkerPool struct {
	workers []*Worker
	ch      chan *Worker
}

func NewWorkerPool(n int) *WorkerPool {
	workers := make([]*Worker, n)
	for i := range workers {
		workers[i] = &Worker{
			id:     i,
			socket: fmt.Sprintf("/tmp/worker_%d.sock", i),
		}
	}
	return &WorkerPool{
		workers: workers,
		ch:      make(chan *Worker, n),
	}
}

func (p *WorkerPool) Start() {
	var wg sync.WaitGroup
	for _, w := range p.workers {
		wg.Add(1)
		go func(w *Worker) {
			defer wg.Done()
			w.spawn()
			p.ch <- w
		}(w)
	}
	wg.Wait()
}

func (w *Worker) spawn() {
	// Clean up stale socket
	if _, err := os.Stat(w.socket); err == nil {
		os.Remove(w.socket)
	}

	// Find the worker script relative to this binary
	exePath, err := os.Executable()
	if err != nil {
		panic(err)
	}
	workerScript := filepath.Join(filepath.Dir(exePath), "worker", "worker.py")

	w.cmd = exec.Command("python3", workerScript)
	w.cmd.Env = append(os.Environ(),
		"WORKER_SOCKET="+w.socket,
		"WORKER_ID="+fmt.Sprintf("%d", w.id),
	)
	w.cmd.Stderr = os.Stderr // surface Python errors

	stdout, err := w.cmd.StdoutPipe()
	if err != nil {
		panic(fmt.Sprintf("worker %d stdout pipe: %v", w.id, err))
	}

	if err := w.cmd.Start(); err != nil {
		panic(fmt.Sprintf("worker %d start: %v", w.id, err))
	}

	// Wait for READY signal (Python prints it after loading models)
	scanner := bufio.NewScanner(stdout)
	ready := make(chan struct{})
	go func() {
		for scanner.Scan() {
			line := scanner.Text()
			if line == "READY" {
				close(ready)
				return
			}
			log.Printf("[worker %d] %s", w.id, line)
		}
	}()

	select {
	case <-ready:
		log.Printf("[worker %d] ready", w.id)
	case <-time.After(120 * time.Second):
		panic(fmt.Sprintf("worker %d timed out waiting for READY", w.id))
	}

	// Connect to the Unix socket
	var conn net.Conn
	for attempts := 0; attempts < 20; attempts++ {
		conn, err = net.Dial("unix", w.socket)
		if err == nil {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	if err != nil {
		panic(fmt.Sprintf("worker %d socket connect: %v", w.id, err))
	}
	w.conn = conn
}

func (p *WorkerPool) Dispatch(req PredictRequest) (*PredictResponse, error) {
	w := <-p.ch
	defer func() { p.ch <- w }()
	return w.infer(req)
}

func (w *Worker) infer(req PredictRequest) (*PredictResponse, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal: %w", err)
	}

	// Send: 4-byte LE length + JSON body
	lenBuf := make([]byte, 4)
	binary.LittleEndian.PutUint32(lenBuf, uint32(len(body)))
	if _, err := w.conn.Write(lenBuf); err != nil {
		return nil, fmt.Errorf("send len: %w", err)
	}
	if _, err := w.conn.Write(body); err != nil {
		return nil, fmt.Errorf("send body: %w", err)
	}

	// Recv: 4-byte LE length + JSON body
	if _, err := io.ReadFull(w.conn, lenBuf); err != nil {
		return nil, fmt.Errorf("recv len: %w", err)
	}
	respLen := binary.LittleEndian.Uint32(lenBuf)
	respBody := make([]byte, respLen)
	if _, err := io.ReadFull(w.conn, respBody); err != nil {
		return nil, fmt.Errorf("recv body: %w", err)
	}

	var resp PredictResponse
	if err := json.Unmarshal(respBody, &resp); err != nil {
		return nil, fmt.Errorf("unmarshal: %w", err)
	}
	return &resp, nil
}

// Ensure we use all CPUs
var _ = runtime.NumCPU
