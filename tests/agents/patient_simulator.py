"""
Patient simulator agent.

Loads a persona-card (clinical case + personality + dialect + emotion) and
acts as the parent/caregiver responding to the chatbot. Mandates SHORT,
human, dialect-coloured replies — the simulator must NEVER sound like an
AI and must NEVER dump the whole case in one turn.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from fever_routing.utils import ModelFactory
except Exception:  # pragma: no cover
    ModelFactory = None  # type: ignore[assignment]


PERSONAS_DIR = Path(__file__).parent / "personas"


@dataclass
class Persona:
    name: str  # name of the persona file (without .yaml)
    category: str  # critical | home | secondary | ambiguous
    dialect: str  # paisa | costeño | rolo | caleño | neutral
    emotion: str  # panic | calm_worry | exhausted | skeptical | grateful | distracted | overwhelmed
    parent_role: str  # mamá | papá | abuela | tío
    case: dict = field(default_factory=dict)
    expected_routing: str = "recommendation"  # recommendation | urgency
    notes: str = ""

    @classmethod
    def load(cls, path: Path | str) -> "Persona":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            name=path.stem,
            category=data.get("category", "home"),
            dialect=data.get("dialect", "neutral"),
            emotion=data.get("emotion", "calm_worry"),
            parent_role=data.get("parent_role", "mamá"),
            case=data.get("case", {}),
            expected_routing=data.get("expected_routing", "recommendation"),
            notes=data.get("notes", ""),
        )

    @classmethod
    def load_all(cls, category: str | None = None) -> list["Persona"]:
        out: list[Persona] = []
        for p in sorted(PERSONAS_DIR.glob("*.yaml")):
            persona = cls.load(p)
            if category is None or persona.category == category:
                out.append(persona)
        return out


_DIALECT_HINTS = {
    "paisa": "Antioquia. 'parce', 'pues', 'mijo', 'qué pena', 'me hace el favor', 'una bobadita', sin yeísmo fuerte.",
    "costeño": "Caribe. 'mi vida', 'ajá', 'eche', 'el pelao', 'mami', acortas palabras, alegre incluso preocupada.",
    "rolo": "Bogotá. 'doctor', 'qué pena con usted', 'le cuento que', tono más formal, tuteas o usted mezclado.",
    "caleño": "Valle. 'mi'jo', 'mirá ve', 'qué tal', 'esa vaina', tono cantadito.",
    "neutral": "Español colombiano estándar, sin marcas regionales fuertes.",
}

_EMOTION_HINTS = {
    "panic": "Estás muy asustada. Frases entrecortadas. A veces preguntas '¿es grave?'. Te tiembla la voz.",
    "calm_worry": "Preocupada pero serena. Respondes lo justo. A veces dudas si tu pelao está bien.",
    "exhausted": "Llevas días sin dormir. Suspiras. Respondes corto, a veces te confundes en datos.",
    "skeptical": "Crees que no es nada grave. Minimizas. 'eso se le pasa solo'. Te molesta dar tantos datos.",
    "grateful": "Agradeces a cada rato. Haces preguntas tipo '¿gracias, doctor, y le doy paracetamol o no?'.",
    "distracted": "Estás haciendo otras cosas. Respondes incompleto, a veces confundes datos y los corriges turnos después.",
    "overwhelmed": "Hijo enfermo + otros niños llorando + casa caótica. Respondes apurada, a veces sin completar frases.",
}


SIMULATOR_SYSTEM = """Estás simulando ser una mamá/papá colombiano hablando por WhatsApp con un pediatra de un servicio gratuito de orientación pediátrica.

REGLAS DURAS (no las rompas):
- Respuestas MUY cortas (máximo 25 palabras / 1-2 frases). Sin listas, sin tecnicismos médicos.
- NUNCA uses palabras de doctor (taquipnea, cianosis, petequias, hemodinámico). Usas frases de mamá real.
- NUNCA des toda la información del caso de golpe — entrega los datos GOTA A GOTA, sólo cuando te pregunten.
- Si te preguntan algo que no es del caso, responde con honestidad parcial o dudando.
- A veces preguntas de vuelta ("¿eso es grave?", "¿le doy algo doctor?").
- Si el pediatra te dice que vayan a urgencias, primero podrías dudar o preguntar "¿en serio?", "¿no es exagerado?".
- Eres humano, no perfecto: a veces das un dato impreciso y luego lo corriges.
- Mantén tu dialecto y tu emoción dominante.

NO digas "soy una IA". NO te disculpes por nada. Suena como una mamá/papá real escribiendo desde el celular."""


@dataclass
class PatientSimulator:
    persona: Persona
    rng: random.Random = field(default_factory=lambda: random.Random(13))

    def __post_init__(self) -> None:
        if ModelFactory is None:
            raise RuntimeError("ModelFactory unavailable — check imports.")
        self._llm = ModelFactory.get_test_agent_model(temperature=0.85)

    def _persona_card(self) -> str:
        case = self.persona.case
        case_block = yaml.safe_dump(case, allow_unicode=True, sort_keys=False)
        return (
            f"DIALECTO: {self.persona.dialect} — {_DIALECT_HINTS.get(self.persona.dialect, '')}\n"
            f"EMOCIÓN DOMINANTE: {self.persona.emotion} — {_EMOTION_HINTS.get(self.persona.emotion, '')}\n"
            f"ROL: eres {self.persona.parent_role} del paciente.\n\n"
            f"CASO CLÍNICO REAL DE TU PELAO/PELADITA (no se lo dices al pediatra de una sola; lo entregas según pregunten):\n"
            f"{case_block}\n"
            f"NOTAS: {self.persona.notes}\n"
        )

    def opening_message(self) -> str:
        case = self.persona.case
        chief = case.get("chief_complaint") or "mi hijo/a tiene fiebre"
        # The persona's chief_complaint IS the realistic opener. Reformulate it
        # in dialect/emotion but DON'T drop critical content (rashes, seizures,
        # cyanosis, fall, etc) — a real parent would mention these immediately.
        prompt = (
            f"{self._persona_card()}\n"
            f"Acabas de entrar al chat. Tu queja inicial al pediatra es esta:\n"
            f"  \"{chief}\"\n\n"
            f"Reformulá esa frase con tu dialecto y emoción, máximo 25 palabras. "
            f"PRESERVÁ el síntoma o evento crítico mencionado (si aparece convulsión, manchitas, "
            f"caída, golpe, cirugía, leucemia, etc., NO lo omitas — un padre real lo dice de una)."
        )
        try:
            response = self._llm.invoke([("system", SIMULATOR_SYSTEM), ("user", prompt)])
            return (response.content if hasattr(response, "content") else str(response)).strip()
        except Exception:
            return f"Doctor, {chief}"

    def respond(self, transcript: list[dict]) -> str:
        """Given the conversation so far, generate the parent's next short reply.

        transcript: list of {"role": "user"|"assistant", "content": str}
        """
        convo_lines: list[str] = []
        for turn in transcript[-10:]:
            who = "Yo (papá/mamá)" if turn["role"] == "user" else "Pediatra"
            convo_lines.append(f"{who}: {turn['content']}")
        convo = "\n".join(convo_lines)

        user_count = sum(1 for t in transcript if t["role"] == "user")
        case = self.persona.case
        pattern_hint = ""
        # Inject conversational patterns at the right turns.
        if case.get("emotional_pattern") and 1 <= user_count <= 2:
            pattern_hint = (
                "\n\nIMPORTANTE: en este turno, en lugar de dar el dato técnico, "
                "expresá miedo o impotencia (ej: 'pero estoy preocupada, qué hago', "
                "'es que me da mucho miedo doctor'). Después de la contención sí "
                "responderás los datos en turnos siguientes."
            )
        if case.get("question_pattern") and user_count in (2, 4, 6):
            pattern_hint = (
                "\n\nIMPORTANTE: este turno, hacele al pediatra una PREGUNTA DIRECTA "
                "('¿es grave?', '¿qué le doy?', '¿debo llevarlo al hospital?') antes "
                "de responder lo que él te preguntó."
            )
        if case.get("frustration_pattern") and user_count >= 4:
            pattern_hint = (
                "\n\nIMPORTANTE: ya estás frustrado/a con tantas preguntas. Mostralo: "
                "'¿cuántas preguntas más?', 'ya le dije todo', 'mejor llevarlo al pediatra'."
            )
        if case.get("cascade_pattern") and user_count >= 2:
            pattern_hint = (
                "\n\nIMPORTANTE: tu pánico está escalando. Intercala datos clínicos "
                "con frases de pánico ('estoy temblando', 'qué hago doctor', '¿es muy malo?')."
            )
        if case.get("late_disclosure") and 3 <= user_count <= 5 and not case.get("_disclosed"):
            disclosure = case.get("late_disclosure")
            case["_disclosed"] = True  # mark so we only do it once
            pattern_hint = (
                f"\n\nIMPORTANTE: este turno DEBES REVELAR este síntoma que olvidaste contar antes: "
                f"\"{disclosure}\". Decílo como 'ah doctor, por cierto…' o 'ay, ya recordé, …' integrado "
                f"en tu mensaje. NO podés omitirlo."
            )

        user_prompt = (
            f"{self._persona_card()}\n\n"
            f"CONVERSACIÓN HASTA AHORA:\n{convo}\n\n"
            f"Generá SÓLO tu próxima respuesta como mamá/papá real. Máximo 25 palabras. "
            f"Respondé sólo lo que el pediatra te pregunta — no adelantes información."
            f"{pattern_hint}"
        )
        try:
            response = self._llm.invoke([("system", SIMULATOR_SYSTEM), ("user", user_prompt)])
            return (response.content if hasattr(response, "content") else str(response)).strip()
        except Exception:
            return "no sé doctor, ahí mismo"
