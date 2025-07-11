class Audiobank:
    def __init__(self, bankmeta_bytes: bytearray, bank_bytes: bytearray):
        if len(bankmeta_bytes) != 8:
            raise Exception()

        self.sample_medium: int   = bankmeta_bytes[0]
        self.seq_player: int      = bankmeta_bytes[1]
        self.table_id: int        = bankmeta_bytes[2]
        self.font_id: int         = bankmeta_bytes[3]
        self.num_instruments: int = bankmeta_bytes[4]
        self.num_drums: int       = bankmeta_bytes[5]
        self.num_effects: int     = int.from_bytes(bankmeta_bytes[6:8], 'big')

        self.instruments: list[Instrument] = []
        self.drums: list[Drum]             = []
        self.effects: list[SoundEffect]    = []

        for i in range(0, self.num_instruments):
            offset = 0x8 + (0x4 * i)
            instrument_offset = int.from_bytes(bank_bytes[offset:offset + 4], 'big')
            instrument = Instrument(i, instrument_offset, bank_bytes) if instrument_offset != 0 else None
            self.instruments.append(instrument)

        drumlist_offset = int.from_bytes(bank_bytes[0:4], 'big')
        for i in range(0, self.num_drums):
            offset = drumlist_offset + (0x4 * i)
            drum_offset = int.from_bytes(bank_bytes[offset:offset + 4], 'big')
            drum = Drum(i, drum_offset, bank_bytes) if drum_offset != 0 else None
            self.drums.append(drum)

        sfxlist_offset = int.from_bytes(bank_bytes[4:8], 'big')
        for i in range(0, self.num_effects):
            offset = sfxlist_offset + (8 * i)
            effect = SoundEffect(i, offset, bank_bytes) if offset != 0 else None
            self.effects.append(effect)

    def get_bank_samples(self):
        all_samples = []

        for instrument in self.instruments:
            if instrument is not None:
                if instrument.low_sample is not None:
                    all_samples.append(instrument.low_sample)
                if instrument.prim_sample is not None:
                    all_samples.append(instrument.prim_sample)
                if instrument.high_sample is not None:
                    all_samples.append(instrument.high_sample)

        for drum in self.drums:
            if drum is not None and drum.sample is not None:
                all_samples.append(drum.sample)

        for effect in self.effects:
            if effect is not None and effect.sample is not None:
                all_samples.append(effect.sample)

        return all_samples


class Instrument:
    def __init__(self, instrument_index: int, instrument_offset: int, bank_bytes: bytearray):
        self.index = instrument_index
        self.low_sample_offset = int.from_bytes(bank_bytes[instrument_offset + 8: instrument_offset + 12], 'big')
        self.prim_sample_offset = int.from_bytes(bank_bytes[instrument_offset + 16: instrument_offset + 20], 'big')
        self.high_sample_offset = int.from_bytes(bank_bytes[instrument_offset + 24: instrument_offset + 28], 'big')

        self.low_sample = Sample(self.low_sample_offset, bank_bytes, self.index, self, "LOW") if self.low_sample_offset != 0 else None
        self.prim_sample = Sample(self.prim_sample_offset, bank_bytes, self.index, self, "PRIM") if self.prim_sample_offset != 0 else None
        self.high_sample = Sample(self.high_sample_offset, bank_bytes, self.index, self, "HIGH") if self.high_sample_offset != 0 else None


class Drum:
    def __init__(self, drum_index: int, drum_offset: int, bank_bytes: bytearray):
        self.index = drum_index
        self.sample_offset = int.from_bytes(bank_bytes[drum_offset + 4:drum_offset + 8], 'big')
        self.sample = Sample(self.sample_offset, bank_bytes, self.index, self)


class SoundEffect:
    def __init__(self, effect_index: int, effect_offset: int, bank_bytes: bytearray):
        self.index = effect_index
        self.sample_offset = int.from_bytes(bank_bytes[effect_offset:effect_offset + 4], 'big')
        self.sample = Sample(self.sample_offset, bank_bytes, self.index, self)


class Sample:
    def __init__(self, sample_offset: int, bank_bytes: bytearray, parent_index: int, parent: Instrument | Drum, key_region: str = None):
        self.parent = parent
        if isinstance(self.parent, Instrument):
            self.parent_type = "INST"
        elif isinstance(self.parent, Drum):
            self.parent_type = "DRUM"
        elif isinstance(self.parent, SoundEffect):
            self.parent_type = "SFX"

        self.parent_index = parent_index
        self.key_region = key_region

        self.address = int.from_bytes(bank_bytes[sample_offset + 4:sample_offset + 8], 'big')
