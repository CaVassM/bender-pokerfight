// Comando campeonato: simula UNA clasificatoria completa con el motor real del kit (docs/competencia.md):
//
//   - cada bot empieza con 10 000 fichas, ciegas fijas 50/100;
//   - mesas de 5 jugadores sorteadas en cada ronda (si la división no es exacta, algunas de 6);
//   - cada mesa juega hasta 50 manos o hasta que quede un solo bot con fichas;
//   - el que se queda sin fichas queda eliminado y no juega más rondas;
//   - tras cada ronda se vuelven a sortear las mesas y cada bot CONSERVA sus fichas (mesa.ConfigPartida.StackPorJugador);
//   - 10 rondas; al final pasan a la final los 6 con más fichas (si quedan menos de 6 con fichas, los últimos eliminados).
//
// El kit no trae este formato (la arena solo hace round-robin y mesa única); este comando lo arma con las mismas
// piezas (internal/mesa y internal/crupier) y no toca nada del kit. Vive en bender/herramientas/ y se compila a bin/:
//
//	go build -o bin/campeonato.exe ./bender/herramientas/campeonato
//
// Uso: campeonato -config torneo.json -salida resultado.json
//
// No se modela el tope de 6 minutos por mesa (nuestras mesas tardan segundos) y cada mesa lanza procesos nuevos para
// los bots (en el campeonato real cada bot mantiene una sola conexión; el alias SÍ es estable entre rondas).
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	mrand "math/rand"
	"os"
	"os/exec"
	"runtime"
	"sort"
	"strconv"
	"sync"
	"time"

	"github.com/aicspucp/pokerfight-arena-participantes/internal/crupier"
	"github.com/aicspucp/pokerfight-arena-participantes/internal/mesa"
)

// Part es un participante del campo. `Tipo` es la etiqueta para el análisis (por ejemplo "base" o "bender");
// el bot no la ve: solo ve su alias `ID`.
type Part struct {
	ID         string   `json:"id"`
	Tipo       string   `json:"tipo"`
	Comando    []string `json:"comando"`
	Directorio string   `json:"directorio,omitempty"`
	Entorno    []string `json:"entorno,omitempty"`
}

type Config struct {
	Semilla       uint64 `json:"semilla"`
	Rondas        int    `json:"rondas"`
	Manos         int64  `json:"manos"`
	CiegaChica    uint64 `json:"ciega_chica"`
	CiegaGrande   uint64 `json:"ciega_grande"`
	Stack         uint64 `json:"stack"`
	TimeoutMs     uint64 `json:"timeout_ms"`
	EsperaMs      uint64 `json:"espera_ms"`
	MaxMesaS      int    `json:"max_mesa_s"`
	Participantes []Part `json:"participantes"`
}

type JugRes struct {
	ID       string `json:"id"`
	Tipo     string `json:"tipo"`
	Antes    uint64 `json:"antes"`
	Despues  uint64 `json:"despues"`
	Timeouts uint64 `json:"timeouts"`
	Manos    uint64 `json:"manos"`
	Posicion int    `json:"posicion"`
}

type MesaRes struct {
	ID        string   `json:"id"`
	Ronda     int      `json:"ronda"`
	Jugadores []JugRes `json:"jugadores"`
	Jugadas   uint64   `json:"manos_jugadas"`
	Error     string   `json:"error,omitempty"`
	DuracionS float64  `json:"duracion_s"`
}

type FinalRes struct {
	ID          string `json:"id"`
	Tipo        string `json:"tipo"`
	Fichas      uint64 `json:"fichas"`
	EliminadoEn int    `json:"eliminado_en"` // 0 = sigue con fichas al terminar
	Puesto      int    `json:"puesto"`
}

type Salida struct {
	Semilla uint64      `json:"semilla"`
	Rondas  [][]MesaRes `json:"rondas"`
	Final   []FinalRes  `json:"final"`
}

func main() {
	rutaCfg := flag.String("config", "", "archivo JSON del campeonato")
	rutaSalida := flag.String("salida", "", "archivo JSON donde escribir el resultado")
	verboso := flag.Bool("verboso", false, "muestra el avance")
	flag.Parse()
	if *rutaCfg == "" || *rutaSalida == "" {
		log.Fatal("uso: campeonato -config torneo.json -salida resultado.json")
	}
	cfg, err := leerConfig(*rutaCfg)
	if err != nil {
		log.Fatalf("campeonato: %v", err)
	}
	salida := correr(cfg, *verboso)
	datos, _ := json.MarshalIndent(salida, "", " ")
	if err := os.WriteFile(*rutaSalida, datos, 0o644); err != nil {
		log.Fatalf("campeonato: no se pudo escribir %s: %v", *rutaSalida, err)
	}
}

func leerConfig(ruta string) (Config, error) {
	var cfg Config
	datos, err := os.ReadFile(ruta)
	if err != nil {
		return cfg, err
	}
	if err := json.Unmarshal(datos, &cfg); err != nil {
		return cfg, err
	}
	if cfg.Rondas <= 0 {
		cfg.Rondas = 10
	}
	if cfg.Manos <= 0 {
		cfg.Manos = 50
	}
	if cfg.CiegaChica == 0 {
		cfg.CiegaChica, cfg.CiegaGrande = 50, 100
	}
	if cfg.Stack == 0 {
		cfg.Stack = 10000
	}
	if cfg.TimeoutMs == 0 {
		cfg.TimeoutMs = 5000
	}
	if cfg.EsperaMs == 0 {
		cfg.EsperaMs = 30000
	}
	if cfg.MaxMesaS == 0 {
		cfg.MaxMesaS = 300
	}
	if len(cfg.Participantes) < 2 {
		return cfg, fmt.Errorf("hacen falta al menos 2 participantes")
	}
	return cfg, nil
}

// repartir divide a los que siguen en mesas de 5 (algunas de 6 si la división no es exacta). Con pocos jugadores
// se usan mesas más chicas; nunca más de 6.
func repartir(ids []string) [][]string {
	n := len(ids)
	k := n / 5
	if k < 1 {
		k = 1
	}
	if n > 6*k {
		k = (n + 5) / 6
	}
	out := make([][]string, k)
	base, extra, idx := n/k, n%k, 0
	for i := 0; i < k; i++ {
		tam := base
		if i < extra {
			tam++
		}
		out[i] = ids[idx : idx+tam]
		idx += tam
	}
	return out
}

func correr(cfg Config, verboso bool) Salida {
	porID := map[string]Part{}
	vivos := []string{}
	fichas := map[string]uint64{}
	elim := map[string]int{}
	puestoEnMesa := map[string]int{} // posición dentro de la mesa donde fue eliminado (desempate)
	for _, p := range cfg.Participantes {
		porID[p.ID] = p
		vivos = append(vivos, p.ID)
		fichas[p.ID] = cfg.Stack
	}
	rng := mrand.New(mrand.NewSource(int64(cfg.Semilla)))
	salida := Salida{Semilla: cfg.Semilla}

	for r := 1; r <= cfg.Rondas && len(vivos) >= 2; r++ {
		rng.Shuffle(len(vivos), func(i, j int) { vivos[i], vivos[j] = vivos[j], vivos[i] })
		grupos := repartir(append([]string(nil), vivos...))
		resultados := make([]MesaRes, len(grupos))
		var espera sync.WaitGroup
		for gi, g := range grupos {
			espera.Add(1)
			semilla := cfg.Semilla*1000003 + uint64(r)*1009 + uint64(gi)
			go func(gi int, g []string, semilla uint64) {
				defer espera.Done()
				miembros := make([]Part, len(g))
				stacks := map[string]uint64{}
				for i, id := range g {
					miembros[i] = porID[id]
					stacks[id] = fichas[id]
				}
				resultados[gi] = jugarMesa(cfg, fmt.Sprintf("r%d-m%d", r, gi+1), r, miembros, stacks, semilla)
			}(gi, g, semilla)
		}
		espera.Wait()
		for _, res := range resultados {
			for _, j := range res.Jugadores {
				fichas[j.ID] = j.Despues
				if j.Despues == 0 {
					elim[j.ID] = r
					puestoEnMesa[j.ID] = j.Posicion
				}
			}
		}
		nuevos := vivos[:0]
		for _, id := range vivos {
			if fichas[id] > 0 {
				nuevos = append(nuevos, id)
			}
		}
		vivos = nuevos
		salida.Rondas = append(salida.Rondas, resultados)
		if verboso {
			fmt.Fprintf(os.Stderr, "campeonato: ronda %d lista, quedan %d con fichas\n", r, len(vivos))
		}
	}

	// Clasificación: primero los que siguen con fichas (más fichas, mejor); luego los eliminados, el último en caer es
	// el mejor (misma ronda: mejor posición dentro de su mesa).
	ids := make([]string, 0, len(porID))
	for id := range porID {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(a, b int) bool {
		ia, ib := ids[a], ids[b]
		va, vb := fichas[ia] > 0, fichas[ib] > 0
		if va != vb {
			return va
		}
		if va {
			if fichas[ia] != fichas[ib] {
				return fichas[ia] > fichas[ib]
			}
			return ia < ib
		}
		if elim[ia] != elim[ib] {
			return elim[ia] > elim[ib]
		}
		if puestoEnMesa[ia] != puestoEnMesa[ib] {
			return puestoEnMesa[ia] < puestoEnMesa[ib]
		}
		return ia < ib
	})
	for i, id := range ids {
		salida.Final = append(salida.Final, FinalRes{ID: id, Tipo: porID[id].Tipo, Fichas: fichas[id], EliminadoEn: elim[id], Puesto: i + 1})
	}
	return salida
}

func token() string {
	var b [12]byte
	_, _ = rand.Read(b[:])
	return "t-" + hex.EncodeToString(b[:])
}

// matar corta el proceso y sus hijos (en Windows el python del venv lanza un hijo: con Kill quedaría huérfano).
func matar(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	if runtime.GOOS == "windows" {
		_ = exec.Command("taskkill", "/F", "/T", "/PID", strconv.Itoa(cmd.Process.Pid)).Run()
	} else {
		_ = cmd.Process.Kill()
	}
}

func jugarMesa(cfg Config, idMesa string, ronda int, miembros []Part, stacks map[string]uint64, semilla uint64) MesaRes {
	inicio := time.Now()
	res := MesaRes{ID: idMesa, Ronda: ronda}
	for _, p := range miembros {
		res.Jugadores = append(res.Jugadores, JugRes{ID: p.ID, Tipo: p.Tipo, Antes: stacks[p.ID], Despues: stacks[p.ID]})
	}
	fallo := func(formato string, args ...any) MesaRes {
		res.Error = fmt.Sprintf(formato, args...)
		res.DuracionS = time.Since(inicio).Seconds()
		return res
	}

	porToken := map[string]Part{}
	tokens := map[string]string{}
	sillas := map[string]int{}
	orden := mrand.New(mrand.NewSource(int64(semilla))).Perm(len(miembros)) // sillas al azar, fijadas por la mesa
	for i, p := range miembros {
		t := token()
		porToken[t], tokens[p.ID] = p, t
		sillas[p.ID] = orden[i]
	}
	n := len(miembros)
	m := mesa.NuevaMesa(idMesa, mesa.ConfigMesa{
		MaxJugadores: uint8(n), MinJugadores: uint8(n), Timeout: cfg.TimeoutMs,
	}, mesa.ConfigPartida{
		CiegaMenor: cfg.CiegaChica, CiegaMayor: cfg.CiegaGrande, StackInicial: cfg.Stack,
		CantidadRondas: cfg.Manos, StackPorJugador: stacks,
	}, crupier.NuevoConSemilla(semilla))

	servidor := mesa.NuevoServidor(mesa.ConfigServidor{
		Direccion: "127.0.0.1:0", TimeoutHandshakeMs: cfg.EsperaMs, MaxConexiones: n,
		Log:     log.New(io.Discard, "", 0),
		SillaDe: func(id string) (int, bool) { s, ok := sillas[id]; return s, ok },
	}, m, func(t string) (string, string, error) {
		p, ok := porToken[t]
		if !ok {
			return "", "", fmt.Errorf("token desconocido")
		}
		return p.ID, p.ID, nil
	})
	if err := servidor.Abrir(); err != nil {
		return fallo("no se pudo abrir el puerto: %v", err)
	}
	defer servidor.Cerrar()
	ctx, cancelar := context.WithTimeout(context.Background(), time.Duration(cfg.MaxMesaS)*time.Second)
	defer cancelar()
	go func() { _ = servidor.Servir(ctx) }()

	var procesos []*exec.Cmd
	defer func() { // pase lo que pase, no dejar procesos vivos
		for _, c := range procesos {
			matar(c)
			_ = c.Wait()
		}
	}()
	for _, p := range miembros {
		if len(p.Comando) == 0 {
			return fallo("el participante %s no tiene comando", p.ID)
		}
		args := append(append([]string(nil), p.Comando[1:]...), "-addr", servidor.Direccion(), "-token", tokens[p.ID])
		c := exec.Command(p.Comando[0], args...)
		c.Dir = p.Directorio
		if len(p.Entorno) > 0 {
			c.Env = append(os.Environ(), p.Entorno...)
		}
		c.Stdout, c.Stderr = io.Discard, io.Discard
		if err := c.Start(); err != nil {
			return fallo("no se pudo lanzar %s: %v", p.ID, err)
		}
		procesos = append(procesos, c)
	}

	limite := time.After(time.Duration(cfg.EsperaMs) * time.Millisecond)
	tick := time.NewTicker(20 * time.Millisecond)
	defer tick.Stop()
	for m.Sentados() < n {
		select {
		case <-limite:
			return fallo("no se conectaron todos (%d de %d)", m.Sentados(), n)
		case <-tick.C:
		}
	}

	resumen, err := m.Jugar(ctx)
	servidor.Cerrar()
	if err != nil {
		res.Error = err.Error()
	}
	res.Jugadas = resumen.CantidadRondasJugadas
	porID := map[string]*JugRes{}
	for i := range res.Jugadores {
		porID[res.Jugadores[i].ID] = &res.Jugadores[i]
	}
	for _, pos := range resumen.Posiciones {
		if j, ok := porID[pos.IDJugador]; ok {
			j.Despues, j.Timeouts, j.Manos, j.Posicion = pos.SaldoFinal, pos.Timeouts, pos.ManosJugadas, pos.Posicion
		}
	}
	res.DuracionS = time.Since(inicio).Seconds()
	return res
}
