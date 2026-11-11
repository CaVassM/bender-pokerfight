// Contraste del evaluador de Bender (phevaluator) contra el evaluador oficial
// de la mesa (pkg/poker). Lee de stdin una mano de 7 cartas por línea (ids
// 0..51, id = (rango-2)*4 + palo) y escribe el Puntaje de pkg/poker, que es el
// que decide los showdowns reales. Lo usa pruebas/test_evaluador_vs_mesa.py.
//
// Vive dentro de bender/ y no modifica nada del kit: solo importa sus paquetes.
package main

import (
	"bufio"
	"fmt"
	"os"

	"github.com/aicspucp/pokerfight-arena-participantes/internal/protocolo"
	"github.com/aicspucp/pokerfight-arena-participantes/pkg/poker"
)

func main() {
	entrada := bufio.NewScanner(os.Stdin)
	salida := bufio.NewWriter(os.Stdout)
	defer salida.Flush()

	for entrada.Scan() {
		var ids [7]int
		n, _ := fmt.Sscan(entrada.Text(), &ids[0], &ids[1], &ids[2], &ids[3], &ids[4], &ids[5], &ids[6])
		if n != 7 {
			fmt.Fprintln(salida, -1)
			continue
		}
		cartas := make([]protocolo.Carta, 7)
		for i, id := range ids {
			cartas[i] = protocolo.Carta{Rango: protocolo.Rango(id/4 + 2), Palo: protocolo.Palo(id % 4)}
		}
		ev, err := poker.MejorDe(cartas)
		if err != nil {
			fmt.Fprintln(salida, -1)
			continue
		}
		fmt.Fprintln(salida, ev.Puntaje)
	}
}
