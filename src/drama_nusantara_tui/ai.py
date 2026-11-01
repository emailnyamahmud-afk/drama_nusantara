"""
AI Provider abstraction — support mock mode (untuk dev/test) dan real Gemini API.

Strategi:
- Mock mode: return template panyandra/character/storyboard yang sudah pre-written
  dengan kualitas ~40% (mirip output LLM real). User edit ke 100%.
- Real mode (Phase 3): call Gemini API via google-generativeai SDK.

Konteks spesifik:
- Bahasa Jawa Krama Inggil untuk dialog
- Struktur panatacara/panyandra baku (nuwun → puji syukur → salawat → sapaan hirarkis)
- Era sejarah: mataram_kuno, majapahit, mataram Islam
- Style preset nusantara untuk prompt visual
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


# ============================================================
# TYPES
# ============================================================
@dataclass
class NaskahDraft:
    """Result dari generate_naskah()."""
    format_type: str         # panyandra | panatacara | dialog | narration
    context: str              # konteks acara
    characters: list[str]    # daftar tokoh
    moment: str               # momen spesifik
    raw_draft: str            # output mentah AI (~40% quality)
    estimated_quality: int    # 0-100, default 40


@dataclass
class CharacterExtraction:
    """Result dari extract_characters()."""
    name: str
    role: str                 # protagonist | antagonist | supporting
    appearance: str
    styling: str
    description: str
    voice_style: str          # prompt untuk Omni custom voice


@dataclass
class SceneExtraction:
    name: str
    location: str
    time_of_day: str
    visual_prompt: str
    lighting: str


@dataclass
class PropExtraction:
    name: str
    type: str                  # weapon | clothing | document | jewelry | other
    visual_prompt: str


@dataclass
class StoryboardSegment:
    """1 segment = 1 Omni generation = 10s video."""
    segment_number: int
    title: str
    shot_type: str             # close-up | medium | wide | extreme-close-up
    angle: str                 # eye-level | low-angle | high-angle | side
    movement: str              # fixed | push-in | pull-out | pan | tilt | tracking
    description: str           # narasi visual sub-shot
    atmosphere: str
    omni_prompt: str           # final prompt untuk Omni 1.1 Flash
    duration_sec: int          # default 10
    character_refs: list[str] # list nama karakter
    scene_ref: str             # nama scene
    prop_refs: list[str]      # list nama prop
    dialogue_jawa: str         # dialog Bahasa Jawa Krama
    dialogue_indonesia: str    # terjemahan untuk subtitle
    ambient_sfx: str          # "gamelan jauh, langkah armor"
    bgm_mood: str             # epic | melancholic | tense | triumphant | mysterious
    voice_style: str


# ============================================================
# PROVIDER PROTOCOL
# ============================================================
class AIProvider(Protocol):
    """Interface untuk AI provider (mock atau real)."""

    def generate_naskah(
        self,
        format_type: str,
        context: str,
        characters: list[str],
        moment: str,
        era: str,
        language: str,
    ) -> NaskahDraft:
        ...

    def extract_assets(
        self,
        naskah: str,
        era: str,
    ) -> tuple[list[CharacterExtraction], list[SceneExtraction], list[PropExtraction]]:
        ...

    def generate_storyboard(
        self,
        naskah: str,
        characters: list[CharacterExtraction],
        scenes: list[SceneExtraction],
        props: list[PropExtraction],
        target_duration_sec: int,
        era: str,
        language: str,
    ) -> list[StoryboardSegment]:
        ...

    def generate_image_prompt(
        self,
        asset_type: str,  # character | scene | prop
        asset_data: dict,
        style_preset: str,
    ) -> str:
        ...


# ============================================================
# MOCK PROVIDER — pre-written templates with ~40% quality
# ============================================================
class MockAIProvider:
    """
    Mock AI provider — return pre-written templates dengan kualitas ~40%.

    Tujuan: Phase 2 testing. User bisa jalankan wizard end-to-end tanpa API key.
    """

    def __init__(self):
        self.provider_name = "mock"

    def generate_naskah(
        self,
        format_type: str,
        context: str,
        characters: list[str],
        moment: str,
        era: str,
        language: str,
    ) -> NaskahDraft:
        """Generate draft naskah panyandra/panatacara/dialog dengan kualitas ~40%."""

        if format_type == "panyandra":
            # Template panyandra dengan kualitas ~40%
            # (mirip output LLM: struktur dasar OK, kosakata kasar, tidak ada rima)
            raw = f"""Nuwun kula nuwun dhumateng para tamu ingkang kinurmatan.

Pramila sedaya kita ngaturaken puji syukur dhumateng Gusti Ingkang Maha Agung ingkang sampun maringi kawilujengan, satemah panjenengan sedaya lan kula saged kempal manunggal wonten ing acara {context}.

Salawat dalah salam mugi tetep linuberna dhumateng Kanjeng Nabi Muhammad saw.

Khususipun wonten ing acara menika, kula aturaken pakurmatan dhumateng {", ".join(characters)} ingkang sami hadir. Momen {moment} menika dipun赛前ngati-ati kanthi tanggel jawab ingkang ageng.

Pramila, mugi-mugi acara menika saged lumampah kanthi lancar lan pinaringan berkah saking Gusti Ingkang Maha Kuwasa. Amin.
"""
        elif format_type == "panatacara":
            raw = f"""Assalamualaikum wr. wb., dhumateng para tamu ingkang kinurmatan.

Pramila, wonten ing wiwitan acara {context}, kula minangka panatacara ngaturaken puji syukur dhumateng Gusti Ingkang Maha Agung.

Sarengipun menika, kula aturaken salawat lan salam dhumateng Kanjeng Nabi Muhammad saw.

Wonten ing acara menika, badhe kita tampi {", ".join(characters)} ingkang badhe {moment}. Mugi-mugi acara menika saged dados kenangan ingkang sae.

Makaten atur kula, nuwun.
"""
        elif format_type == "dialog":
            raw = f"""## S01 | DALAM · Pendopo · Senja

Cahaya senja menerobos jendela. {characters[0] if characters else 'Tokoh 1'} berdiri di tengah pendopo, ekspresi tegang.

{characters[0] if characters else 'Tokoh 1'}: (menghela napas) {moment}. Kula ngaturaken pamrayoga...

{characters[1] if len(characters) > 1 else 'Tokoh 2'}: (menunduk hormat) Nuwun, {characters[0] if characters else 'Tokoh 1'}. Kula aturaken laporan.

{characters[0] if characters else 'Tokoh 1'}: (mengangkat tangan) Sampun. Kula ngertos.
"""
        else:  # narration
            raw = f"""Tahun {era}. {context}.

{moment}. {", ".join(characters)} berdiri di tengah kompleks keraton, menatap matahari senja yang meredup.

Sebuah momen yang akan mengubah sejarah Nusantara selamanya.
"""

        return NaskahDraft(
            format_type=format_type,
            context=context,
            characters=characters,
            moment=moment,
            raw_draft=raw,
            estimated_quality=40,
        )

    def extract_assets(
        self,
        naskah: str,
        era: str,
    ) -> tuple[list[CharacterExtraction], list[SceneExtraction], list[PropExtraction]]:
        """Mock extraction — return template assets berdasarkan era."""

        if era == "majapahit":
            characters = [
                CharacterExtraction(
                    name="Gajah Mada",
                    role="protagonist",
                    appearance="Pria Jawa usia 30-an, wajah tegas dengan jenggot tipis, mata tajam, kulit sawo matang, postur tegap 175cm",
                    styling="Blangkon hitam dengan motif batik kawung, beskap hitam dengan kancing perak, kain panjang batik kawung, keris Naga Sasra terselip di pinggang belakang",
                    description="Mahapatih muda Majapahit, ambisius namun berbakti",
                    voice_style="Deep mature Javanese male voice, authoritative but warm, traditional court accent, krama inggil style",
                ),
                CharacterExtraction(
                    name="Prajurit Muda",
                    role="supporting",
                    appearance="Pria Jawa usia 20-an, wajah muda dengan bulu mata panjang, postur tegap 165cm, kulit sawo matang",
                    styling="Armor prajurit Majapahit sederhana, blangkon hitam polos, kain batik parang",
                    description="Prajurit kurir yang membawa berita dari perbatasan",
                    voice_style="Young Javanese male voice, respectful but nervous, krama style",
                ),
            ]
            scenes = [
                SceneExtraction(
                    name="Pendopo Keraton Majapahit",
                    location="Pendopo utama keraton Majapahit, Trowulan",
                    time_of_day="senja",
                    visual_prompt="Candi-era Javanese pendopo with carved teakwood pillars, red roof tiles, stone floor with batik patterns, golden hour light streaming through carved windows, incense smoke",
                    lighting="Golden hour warm sunlight from west windows, long shadows on marble floor, haze from incense",
                )
            ]
            props = [
                PropExtraction(
                    name="Keris Naga Sasra",
                    type="weapon",
                    visual_prompt="Ancient Javanese keris pusaka, damascene blade with dragon pattern, gold hilt with ruby, white background product shot",
                )
            ]
        elif era == "mataram_islam":
            characters = [
                CharacterExtraction(
                    name="Sultan Agung",
                    role="protagonist",
                    appearance="Pria Jawa usia 40-an, jenggot tebal, wajah berkharisma, mata tajam, kulit sawo matang, postur tegap 178cm",
                    styling="Blangkon hitam dengan batik sidomukti, beskap hitam with golden embroidery, kain batik parang kusuma, keris at waist",
                    description="Sultan Mataram ke-3, penakluk teritorial terluas, penyerang Batavia 1628-1629",
                    voice_style="Deep authoritative Javanese male voice, sultan court accent, krama inggil with religious tone",
                ),
            ]
            scenes = [
                SceneExtraction(
                    name="Keraton Mataram",
                    location="Keraton Mataram, Kotagede",
                    time_of_day="subuh",
                    visual_prompt="Javanese keraton architecture with carved teakwood pendopo, batik patterned floor, golden morning mist, traditional mosque minaret in background",
                    lighting="Soft blue dawn light, mist rising from ground, warm candle glow from interior",
                )
            ]
            props = [
                PropExtraction(
                    name="Tombak Kyai Plered",
                    type="weapon",
                    visual_prompt="Ancient Javanese tombak pusaka, silver damascene blade, golden hilt with carvings, white background product shot",
                )
            ]
        else:  # mataram_kuno
            characters = [
                CharacterExtraction(
                    name="Sanjaya",
                    role="protagonist",
                    appearance="Pria Jawa usia 30-an, wajah tegas dengan kumis tipis, mata tajam, kulit sawo matang, postur tegap 175cm",
                    styling="Crown Jawa kuno with golden ornaments, armor perang Hindu-Buddha, kain batik prada",
                    description="Raja Mataram Kuno (732 M), pendiri dinasti Sanjaya, pembangun candi Siwa",
                    voice_style="Deep royal Javanese male voice, ancient court accent, krama inggil with Sanskrit influence",
                ),
            ]
            scenes = [
                SceneExtraction(
                    name="Candi Siwa Prambanan",
                    location="Kompleks candi Prambanan",
                    time_of_day="sore",
                    visual_prompt="Ancient Javanese candi with tall stone towers, carved reliefs of Ramayana, golden hour light, incense smoke, Buddhist-Hindu syncretic atmosphere",
                    lighting="Golden sunset, long shadows, warm orange glow on stone",
                )
            ]
            props = [
                PropExtraction(
                    name="Lingga Yoni",
                    type="other",
                    visual_prompt="Ancient Javanese lingga yoni stone, carved with Hindu motifs, weathered patina, white background product shot",
                )
            ]

        return characters, scenes, props

    def generate_storyboard(
        self,
        naskah: str,
        characters: list[CharacterExtraction],
        scenes: list[SceneExtraction],
        props: list[PropExtraction],
        target_duration_sec: int,
        era: str,
        language: str,
    ) -> list[StoryboardSegment]:
        """Mock storyboard breakdown — split naskah jadi N segment × 10s."""

        num_segments = max(1, target_duration_sec // 10)
        scene = scenes[0] if scenes else None
        char_names = [c.name for c in characters]
        prop_names = [p.name for p in props]

        # Mock segments — template untuk era Majapahit (default)
        if era == "majapahit":
            segment_templates = [
                {
                    "title": "Berita dari Perbatasan",
                    "shot_type": "medium",
                    "angle": "eye-level",
                    "movement": "push-in",
                    "description": f"【镜头1】{char_names[0] if char_names else 'Gajah Mada'} berdiri tegak di {scene.name if scene else 'pendopo'}, tangan kanan memegang hulu keris.\n【镜头2】Pintu pendopo terbuka, {char_names[1] if len(char_names) > 1 else 'Prajurit'} masuk, menunduk hormat.",
                    "atmosphere": "Golden hour light, gamelan jauh, langkah armor berdebu, hawa tegang namun khidmat",
                    "omni_prompt": f"Vertical 9:16. {char_names[0] if char_names else 'Gajah Mada'} (ref: {char_names[0].lower().replace(' ', '_') if char_names else 'gajah_mada'}_turnaround.png) berdiri di {scene.name if scene else 'pendopo Majapahit'} (ref: {scene.name.lower().replace(' ', '_') if scene else 'pendopo_majapahit'}_scene.png). Golden hour light streaming. Dia memegang hulu keris dengan ekspresi tegang. Camera slow push-in dari medium shot. Audio: gamelan jauh, langkah armor. Dialog Bahasa Jawa krama.",
                    "dialogue_jawa": "Ampun, Mahapatih. Wartos saking perbatasan Timur — pamberontakan sampun dipunpungkas.",
                    "dialogue_indonesia": "Ampun, Mahapatih. Berita dari perbatasan Timur — pemberontakan telah dipadamkan.",
                    "ambient_sfx": "Gamelan jauh, langkah armor, angin di pendopo",
                    "bgm_mood": "epic",
                },
                {
                    "title": "Korban dan Kesunyitan",
                    "shot_type": "close-up",
                    "angle": "eye-level",
                    "movement": "fixed",
                    "description": f"【镜头1】Close-up wajah {char_names[0] if char_names else 'Gajah Mada'}, ekspresi berubah dari tegang ke sedih.\n【镜头2】Close-up {char_names[1] if len(char_names) > 1 else 'Prajurit'}, menunduk.\n【镜头3】Wide shot pendopo, sunyi.",
                    "atmosphere": "Senja meredup, hening sepi, denting gamelan terakhir, bayangan panjang di lantai",
                    "omni_prompt": f"Continue: Close-up {char_names[0] if char_names else 'Gajah Mada'} face, expression changes from tense to sad. Cut to close-up {char_names[1] if len(char_names) > 1 else 'prajurit'} menunduk. Cut to wide shot pendopo sunyi. Camera fixed.",
                    "dialogue_jawa": "Tiga atus prajurit gugur, Mahapathi. Kalebet Panglima Tanca.",
                    "dialogue_indonesia": "Tiga ratus prajurit gugur, Mahapatih. Termasuk Panglima Tanca.",
                    "ambient_sfx": "Hening, denting gamelan terakhir",
                    "bgm_mood": "melancholic",
                },
                {
                    "title": "Sumpah Palapa",
                    "shot_type": "extreme-close-up",
                    "angle": "eye-level",
                    "movement": "tilt",
                    "description": f"【镜头1】Extreme close-up mata {char_names[0] if char_names else 'Gajah Mada'}, tajam dan determinan.\n【镜头2】Menghunus keris, mengangkat ke depan wajah. Slow motion.\n【镜头3】Prajurit terkesima, kamera tilt down ke keris. Fade to black.",
                    "atmosphere": "Senja terakhir, dramatis, denting gamelan terakhir, keheningan setelah sumpah",
                    "omni_prompt": f"Continue: Extreme close-up {char_names[0] if char_names else 'Gajah Mada'} eyes, sharp and determined. He draws keris (ref: {props[0].name.lower().replace(' ', '_') if props else 'keris_naga_sasra'}_prop.png), raises to face. Slow motion. Camera tilt down to gleaming keris. Fade to black. Final dramatic gamelan strike.",
                    "dialogue_jawa": "Kula sumerep palapa, ngantos Nusantara manunggal!",
                    "dialogue_indonesia": "Aku bersumpah palapa, sampai Nusantara bersatu!",
                    "ambient_sfx": "Hening dramatis, denting gamelan terakhir",
                    "bgm_mood": "triumphant",
                },
            ]
        else:
            # Generic fallback
            segment_templates = [
                {
                    "title": f"Segment {i+1}",
                    "shot_type": "medium",
                    "angle": "eye-level",
                    "movement": "push-in",
                    "description": f"{char_names[0] if char_names else 'Tokoh'} di {scene.name if scene else 'lokasi'}.",
                    "atmosphere": "Atmosfer generik",
                    "omni_prompt": f"Vertical 9:16. {char_names[0] if char_names else 'Tokoh'} di {scene.name if scene else 'scene'}. Camera push-in.",
                    "dialogue_jawa": "",
                    "dialogue_indonesia": "",
                    "ambient_sfx": "Ambient generik",
                    "bgm_mood": "epic",
                }
                for i in range(num_segments)
            ]

        segments = []
        for i, tmpl in enumerate(segment_templates[:num_segments]):
            seg = StoryboardSegment(
                segment_number=i + 1,
                title=tmpl["title"],
                shot_type=tmpl["shot_type"],
                angle=tmpl["angle"],
                movement=tmpl["movement"],
                description=tmpl["description"],
                atmosphere=tmpl["atmosphere"],
                omni_prompt=tmpl["omni_prompt"],
                duration_sec=10,
                character_refs=char_names,
                scene_ref=scene.name if scene else "",
                prop_refs=prop_names,
                dialogue_jawa=tmpl["dialogue_jawa"],
                dialogue_indonesia=tmpl["dialogue_indonesia"],
                ambient_sfx=tmpl["ambient_sfx"],
                bgm_mood=tmpl["bgm_mood"],
                voice_style=characters[0].voice_style if characters else "",
            )
            segments.append(seg)

        return segments

    def generate_image_prompt(
        self,
        asset_type: str,
        asset_data: dict,
        style_preset: str,
    ) -> str:
        """Generate prompt untuk Nano Banana Pro (di Flow, free unlimited)."""

        # Get style prompt from preset value
        style_prompts = {
            "nusantara-epic": "cinematic historical epic realism with Indonesian Nusantara aesthetic, semi-realistic character art with refined facial features and ethnic accuracy (Javanese, Sundanese, Balinese physiognomy), period-accurate traditional costume, dramatic volumetric lighting with golden-hour warmth",
            "nusantara-classical": "Indonesian classical realist painting style in tradition of Basuki Abdullah, warm naturalistic oil-painting brushwork, earthy palette of sienna, umber, ochre",
            "nusantara-wayang": "Indonesian traditional wayang kulit shadow puppet aesthetic, flat two-dimensional silhouette puppet art with intricate Javanese ornamental perforations",
            "nusantara-batik": "Indonesian batik-inspired decorative illustration, rich earth-tone palette, traditional batik motifs as environmental texture",
        }
        style = style_prompts.get(style_preset, style_prompts["nusantara-epic"])

        if asset_type == "character":
            name = asset_data.get("name", "character")
            appearance = asset_data.get("appearance", "")
            styling = asset_data.get("styling", "")
            return (
                f"Character turnaround reference sheet, 5 angles "
                f"(front close-up, 3/4 left, full frontal, 3/4 right, back view) "
                f"of an Indonesian Javanese character: {name}. "
                f"{appearance}. {styling}. "
                f"Clean pure white background, nusantara-epic cinematic style, vertical 9:16 aspect ratio. "
                f"Style: {style}. "
                f"Avoid anime style, avoid 3D CGI render, avoid plastic look, "
                f"avoid generic Asian face, avoid modern clothing."
            )
        elif asset_type == "scene":
            name = asset_data.get("name", "scene")
            location = asset_data.get("location", "")
            time = asset_data.get("time_of_day", "siang")
            visual = asset_data.get("visual_prompt", "")
            return (
                f"Scene reference image (single angle) of {name}: {location}. "
                f"Time of day: {time}. "
                f"{visual}. "
                f"Style: {style}. "
                f"Vertical 9:16 aspect ratio. "
                f"No characters in frame — pure environment shot."
            )
        elif asset_type == "prop":
            name = asset_data.get("name", "prop")
            visual = asset_data.get("visual_prompt", "")
            return (
                f"Product shot of {name}. {visual}. "
                f"Clean pure white background, top-down or 3/4 angle view. "
                f"Style: realistic photography. "
                f"Avoid cluttered background, avoid other objects."
            )
        return ""


# ============================================================
# REAL GEMINI PROVIDER — Phase 3 (stub)
# ============================================================
class GeminiProvider:
    """Real Gemini API provider — TODO Phase 3."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.provider_name = "gemini"
        # Lazy import — avoid hard dependency di Phase 2
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model)
            except ImportError:
                raise RuntimeError(
                    "google-generativeai tidak terinstall. Run: uv add google-generativeai"
                )
        return self._client

    def generate_naskah(self, *args, **kwargs):
        raise NotImplementedError("Phase 3 — akan diimplementasi dengan Gemini API")

    def extract_assets(self, *args, **kwargs):
        raise NotImplementedError("Phase 3 — akan diimplementasi dengan Gemini API")

    def generate_storyboard(self, *args, **kwargs):
        raise NotImplementedError("Phase 3 — akan diimplementasi dengan Gemini API")

    def generate_image_prompt(self, *args, **kwargs):
        raise NotImplementedError("Phase 3 — akan diimplementasi dengan Gemini API")


# ============================================================
# FACTORY
# ============================================================
def get_ai_provider(use_mock: bool = True, api_key: str = "") -> AIProvider:
    """
    Factory untuk AI provider.

    Args:
        use_mock: True untuk mock mode (Phase 2 dev), False untuk real Gemini
        api_key: Gemini API key (wajib jika use_mock=False)
    """
    if use_mock or not api_key:
        return MockAIProvider()
    return GeminiProvider(api_key=api_key)
