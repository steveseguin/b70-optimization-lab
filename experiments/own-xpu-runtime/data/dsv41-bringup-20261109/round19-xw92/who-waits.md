### Who waits for whom (OWN_XWAIT, 63 steps, ticks -> us at 2400 MHz)

| exchange | per step | last to arrive (share of exchanges) | wait per card, us per step |
|---|---|---|---|
| output-a rows | 40 | c5 69%, c2 30%, c3 1%, c1 0%, c4 0% | c0 915.6, c1 879.2, c2 159.7, c3 856.2, c4 875.7, c5 95.7 |
| output-b rows | 40 | c2 36%, c0 32%, c5 24%, c3 4%, c1 2%, c4 2% | c0 196.3, c1 219.1, c2 187.6, c3 210.7, c4 228.5, c5 227.2 |
| expert activations | 40 | c3 30%, c1 27%, c5 26%, c2 9%, c4 4%, c0 4% | c0 240.3, c1 182.2, c2 220.5, c3 172.2, c4 237.8, c5 174.6 |
| ffn rows | 40 | c2 48%, c5 36%, c0 7%, c1 6%, c4 3%, c3 1% | c0 254.1, c1 250.6, c2 212.0, c3 283.4, c4 249.8, c5 198.8 |
| engram rows | 2 | c0 28%, c2 25%, c1 23%, c3 11%, c5 10%, c4 2% | c0 4.1, c1 4.6, c2 4.8, c3 4.2, c4 5.1, c5 4.8 |

Total wait per step: c0 1610, c1 1536, c2 784, c3 1527, c4 1597, c5 701 us (the least-waiting card sets the pace).

