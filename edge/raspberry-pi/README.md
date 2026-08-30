# Raspberry-Pi-Empfänger

`yamnet_udp_live.py` fasst die kurzen YAMNet-Audiofenster zu Dashboard-Ereignissen
zusammen. Enthält ein Ereignis eine belastbare `Speech`-Erkennung, wird es als
`Speech` gespeichert. Generische Zufallstreffer wie `Animal` oder `Cat` dürfen eine
erkennbare Stimme nicht mehr als primäre Einordnung verdrängen.

Die Audioübertragung und die Rohaufnahmen laufen davon unabhängig weiter.
