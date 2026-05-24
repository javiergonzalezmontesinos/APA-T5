"""Funciones para manipular senales WAVE estereo.

Alumno: Javier Gonzalez

Este modulo permite separar, combinar, codificar y decodificar senales WAVE
PCM usando solamente la biblioteca struct para leer y escribir datos binarios.
"""

import struct


FMT_SIZE = 16
PCM = 1
MONO = 1
STEREO = 2
BITS_16 = 16
BITS_32 = 32


def _lee_wave(fichero):
    """Lee un fichero WAVE PCM y devuelve su cabecera util y sus muestras."""
    with open(fichero, "rb") as entrada:
        riff = entrada.read(12)
        if len(riff) != 12:
            raise ValueError("El fichero no contiene una cabecera RIFF valida")

        marca, _, tipo = struct.unpack("<4sI4s", riff)
        if marca != b"RIFF" or tipo != b"WAVE":
            raise ValueError("El fichero no es un WAVE valido")

        formato = None
        datos = None

        while True:
            cabecera = entrada.read(8)
            if not cabecera:
                break
            if len(cabecera) != 8:
                raise ValueError("Cacho RIFF incompleto")

            nombre, tamanyo = struct.unpack("<4sI", cabecera)
            contenido = entrada.read(tamanyo)
            if len(contenido) != tamanyo:
                raise ValueError("Cacho RIFF truncado")

            if tamanyo % 2:
                entrada.read(1)

            if nombre == b"fmt ":
                if tamanyo < FMT_SIZE:
                    raise ValueError("Subcacho fmt incompleto")
                formato = struct.unpack("<HHIIHH", contenido[:FMT_SIZE])
            elif nombre == b"data":
                datos = contenido

        if formato is None:
            raise ValueError("Falta el subcacho fmt")
        if datos is None:
            raise ValueError("Falta el subcacho data")

        audio_format, canales, frecuencia, _, _, bits = formato
        if audio_format != PCM:
            raise ValueError("Solo se admiten ficheros WAVE PCM lineales")
        if bits not in (BITS_16, BITS_32):
            raise ValueError("Solo se admiten muestras de 16 o 32 bits")

        bytes_muestra = bits // 8
        if len(datos) % (canales * bytes_muestra) != 0:
            raise ValueError("El tamanyo de data no coincide con el formato")

        codigo = "h" if bits == BITS_16 else "i"
        muestras = struct.unpack(
            "<" + codigo * (len(datos) // bytes_muestra),
            datos,
        )

        return {
            "canales": canales,
            "frecuencia": frecuencia,
            "bits": bits,
            "muestras": muestras,
        }


def _escribe_wave(fichero, canales, frecuencia, bits, muestras):
    """Escribe un fichero WAVE PCM con una cabecera canonica."""
    bytes_muestra = bits // 8
    block_align = canales * bytes_muestra
    byte_rate = frecuencia * block_align
    codigo = "h" if bits == BITS_16 else "i"
    datos = struct.pack("<" + codigo * len(muestras), *muestras)
    tamanyo_riff = 4 + (8 + FMT_SIZE) + (8 + len(datos))

    with open(fichero, "wb") as salida:
        salida.write(struct.pack("<4sI4s", b"RIFF", tamanyo_riff, b"WAVE"))
        salida.write(struct.pack("<4sI", b"fmt ", FMT_SIZE))
        salida.write(
            struct.pack(
                "<HHIIHH",
                PCM,
                canales,
                frecuencia,
                byte_rate,
                block_align,
                bits,
            )
        )
        salida.write(struct.pack("<4sI", b"data", len(datos)))
        salida.write(datos)


def _clip16(valor):
    """Limita un entero al rango de una muestra PCM de 16 bits."""
    return max(-32768, min(32767, valor))


def _mitad(valor):
    """Calcula la mitad entera truncando hacia cero."""
    return int(valor / 2)


def estereo2mono(ficEste, ficMono, canal=2):
    """Convierte un WAVE estereo de 16 bits en uno mono de 16 bits."""
    onda = _lee_wave(ficEste)
    if onda["canales"] != STEREO or onda["bits"] != BITS_16:
        raise ValueError("El fichero de entrada debe ser estereo de 16 bits")
    if canal not in (0, 1, 2, 3):
        raise ValueError("El canal debe ser 0, 1, 2 o 3")

    muestras = onda["muestras"]
    pares = zip(muestras[0::2], muestras[1::2])
    operaciones = (
        lambda izquierda, derecha: izquierda,
        lambda izquierda, derecha: derecha,
        lambda izquierda, derecha: _mitad(izquierda + derecha),
        lambda izquierda, derecha: _mitad(izquierda - derecha),
    )
    mono = [operaciones[canal](izquierda, derecha) for izquierda, derecha in pares]

    _escribe_wave(ficMono, MONO, onda["frecuencia"], BITS_16, mono)


def mono2estereo(ficIzq, ficDer, ficEste):
    """Combina dos WAVE mono de 16 bits en un WAVE estereo de 16 bits."""
    izquierda = _lee_wave(ficIzq)
    derecha = _lee_wave(ficDer)

    if izquierda["canales"] != MONO or derecha["canales"] != MONO:
        raise ValueError("Los ficheros de entrada deben ser monofonicos")
    if izquierda["bits"] != BITS_16 or derecha["bits"] != BITS_16:
        raise ValueError("Los ficheros de entrada deben ser de 16 bits")
    if izquierda["frecuencia"] != derecha["frecuencia"]:
        raise ValueError("Las frecuencias de muestreo deben coincidir")
    if len(izquierda["muestras"]) != len(derecha["muestras"]):
        raise ValueError("Los dos canales deben tener la misma duracion")

    estereo = [
        muestra
        for par in zip(izquierda["muestras"], derecha["muestras"])
        for muestra in par
    ]

    _escribe_wave(ficEste, STEREO, izquierda["frecuencia"], BITS_16, estereo)


def codEstereo(ficEste, ficCod):
    """Codifica un WAVE estereo de 16 bits como WAVE mono de 32 bits."""
    onda = _lee_wave(ficEste)
    if onda["canales"] != STEREO or onda["bits"] != BITS_16:
        raise ValueError("El fichero de entrada debe ser estereo de 16 bits")

    pares = zip(onda["muestras"][0::2], onda["muestras"][1::2])
    codificado = [
        (_mitad(izquierda + derecha) << 16)
        | (_mitad(izquierda - derecha) & 0xFFFF)
        for izquierda, derecha in pares
    ]

    _escribe_wave(ficCod, MONO, onda["frecuencia"], BITS_32, codificado)


def decEstereo(ficCod, ficEste):
    """Decodifica un WAVE mono de 32 bits en un WAVE estereo de 16 bits."""
    onda = _lee_wave(ficCod)
    if onda["canales"] != MONO or onda["bits"] != BITS_32:
        raise ValueError("El fichero de entrada debe ser mono de 32 bits")

    semisumas = [muestra >> 16 for muestra in onda["muestras"]]
    semidiferencias = [
        (muestra & 0xFFFF) - 0x10000
        if muestra & 0x8000
        else muestra & 0xFFFF
        for muestra in onda["muestras"]
    ]
    estereo = [
        muestra
        for semisuma, semidiferencia in zip(semisumas, semidiferencias)
        for muestra in (
            _clip16(semisuma + semidiferencia),
            _clip16(semisuma - semidiferencia),
        )
    ]

    _escribe_wave(ficEste, STEREO, onda["frecuencia"], BITS_16, estereo)
