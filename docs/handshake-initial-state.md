# ZOOM LiveTrak L12next – Handshake iniziale e stato completo

## 1. Framing SysEx

Il protocollo proprietario usa:

```text
F0 52 00 00 ... F7
```

`F0` = SysEx start  
`52` = ZOOM manufacturer ID  
`00 00` = prefisso L12next  
`F7` = SysEx end

## 2. Sequenza iniziale

```text
APP/HOST                         L12next
   |                               |
   |-- Enter PC Mode ------------->|
   |-- Identity Request ---------->|
   |<- Firmware / Identity --------|
   |-- Global Dump Request ------->|
   |<- Global State 429 byte ------|
   |-- Patch Info Scene ---------->|
   |<- Elenco Scene ---------------|
   |-- Patch Info EFX ------------>|
   |<- Elenco Preset EFX ----------|
   |-- Fader Mode ---------------->|
   |<- Eventi / Meter realtime ----|
```

## 3. Enter PC Mode

```text
F0 52 00 00 50 F7
```

Comando senza payload. Apre la sessione di controllo remoto.

## 4. Identity / Firmware

Richiesta:

```text
F0 52 00 00 06 F7
```

Risposta:

```text
F0 52 00 00 06 xx xx xx xx F7
```

I 4 byte sono letti dall'app come versione firmware.

## 5. Global Setting Dump

Richiesta:

```text
F0 52 00 00 2B F7
```

Risposta:

```text
F0 52 00 00 2B 2D 03 [429 byte] F7
```

La lunghezza è MIDI-safe 14 bit:

```text
value = low7 | (high7 << 7)

0x2D | (0x03 << 7) = 429
```

Questo è il passaggio principale con cui il mixer invia all'app lo stato iniziale completo.

## 6. Stato globale trasmesso

Il blocco da 429 byte viene copiato nello stato interno:

```text
0x73B3 ... 0x755F
```

Mappa:

```text
0x73B3-0x73B4  USB input select
0x73B5-0x740E  nomi canali
0x740F-0x7418  colori canali
0x7419-0x7422  gain boost
0x7423-0x742C  gain
0x742D-0x7436  compressor
0x7437-0x7440  channel select
0x7441-0x744A  mute
0x744B-0x7454  solo
0x7455-0x745E  phase
0x745F-0x7468  pan
0x7469-0x7472  EQ high
0x7473-0x747C  EQ mid frequency
0x747D-0x7486  EQ mid Q
0x7487-0x7490  EQ mid gain
0x7491-0x749A  EQ low
0x749B-0x74A4  low cut
0x74A5-0x74AE  send EFX

0x74AF-0x74B8  fader
0x74B9-0x74C2  send A
0x74C3-0x74CC  send B
0x74CD-0x74D6  send C
0x74D7-0x74E0  send D
0x74E1-0x74EA  send E

0x74EB          EFX type
0x74EC-0x74ED   EFX parameter 1, 14 bit
0x74EE-0x74EF   EFX parameter 2, 14 bit
0x74F0-0x74F1   EFX auxiliary 14-bit field
0x74F2          EFX mute
0x74F3          EFX solo
0x74F4          EFX return fader
0x74F5-0x74F9   EFX return A-E

0x74FA          Master Mute
0x74FB          Master Comp
0x74FC          Master Fader

0x74FD-0x7501   Monitor A-E
0x7502          Master EQ global ON
0x7503-0x752A   Master EQ, 8 target × 5 campi

0x752B-0x7534   SceneState[10]
0x7535          Scene Reset
0x7536          Scene Save
0x7537          Scene Recall
0x7538          Scene Delete

0x7539-0x755F   Project / Recorder State
```

## 7. Significato pratico

All'avvio il mixer non ricostruisce lo stato inviando centinaia di CC singoli.

Il modello principale è:

```text
APP -> MIXER
richiesta 2B

MIXER -> APP
429 byte di stato completo

APP
copia il blocco nello stato interno e aggiorna la GUI
```

Quindi il Global Setting Dump è una fotografia iniziale globale.

## 8. Global Setting Dump Listener

Esiste anche:

```text
2B 0A
```

L'app applica lo stato globale preservando Monitor A-E.

## 9. Patch Info – Scene

Richiesta:

```text
F0 52 00 00 07 00 F7
```

`00 = library scene`

Risposta:

```text
COUNT:uint14

Per ogni scena:
INDEX:uint14
FLAG:uint8
NAME:17 byte
```

Ogni record occupa 20 byte.

## 10. Patch Info – EFX

Richiesta:

```text
F0 52 00 00 07 01 F7
```

`01 = library efx1`

Il formato record è lo stesso.

## 11. Patch Data Dump

Comando:

```text
08
```

Formato:

```text
F0 52 00 00 08 LIBRARY
A:uint14
LEN:uint14
BLOB:LEN byte
C:uint14
DATA...
F7
```

`A`, `BLOB` e `C` hanno struttura nota ma semantica non esposta chiaramente.

## 12. Scene dump persistente

Per library 0 il payload scena è esattamente **310 byte**.

`CHANNEL SELECT` e `SOLO` sono runtime state e non vengono salvati nella scena persistente.

## 13. Fader Mode

```text
F0 52 00 00 4C MODE F7
```

MODE:

```text
00 MASTER
01 MONITOR A
02 MONITOR B
03 MONITOR C
04 MONITOR D
05 MONITOR E
06 MONITOR F
```

## 14. Aggiornamenti dopo l'handshake

Dopo il dump iniziale da 429 byte il mixer passa agli aggiornamenti incrementali:

```text
01 Parameters
02 Parameters In
03 Parameters14
```

Eventi realtime:

```text
31 00 Project Name Changed
31 01 Scene Changed
31 02 Channel Name Changed
31 03 Channel Color Changed
31 04 Meters Changed
31 05 Display Time
```

## 15. Meter stream

Frame:

```text
F0 52 00 00 31 04 [31 byte] F7
```

Totale: 38 byte.

Payload:

```text
0       fader/meter mode
1..12   nibble-packed signal + companion bank
13..14  EFX/aux
15..26  12 canali
27..28  EFX L/R
29..30  Master L/R
```

Valori wire: `0..15`

Decode:

```text
value & 0x0F
value >> 4
```

## 16. Chiusura sessione

```text
F0 52 00 00 51 F7
```

Terminate PC Mode.

## 17. Riassunto

All'avvio:

1. Enter PC Mode
2. Identity / Firmware
3. Global Setting Dump da 429 byte
4. Patch Info Scene
5. Patch Info EFX
6. Fader Mode

Poi:

- CC singoli
- Parameters / Parameters14
- eventi `31 xx`
- meter `31 04`

Punto fondamentale: il mixer trasmette lo stato iniziale di praticamente tutto principalmente tramite il **Global Setting Dump `2B` da 429 byte**.
