import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL } from "../services/dengueRules";
import type { PatientData } from "../types/patient";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

type SelectOption = { code: number | string; name: string };
type UfOption = { code: number; sigla: string; name: string };
type MunicipioItem = { code: number; name: string; stateCode: number; state: string };
type RegiaoItem = { code: number; name: string; state: string; officialCode?: number };
type AutocompleteItem = { code: number | string; name: string; state?: string; stateCode?: number };

type TriageOptions = {
  sexos: SelectOption[];
  racas: SelectOption[];
  escolaridades: SelectOption[];
  situacoesGestacao: SelectOption[];
  ufs: UfOption[];
};

// ---------------------------------------------------------------------------
// Semana epidemiológica (padrão SINAN: semana começa no domingo)
// ---------------------------------------------------------------------------

function calcularSemanaEpi(data: Date): { semana: number; ano: number } {
  const quarta = new Date(data);
  quarta.setUTCDate(data.getUTCDate() + (3 - data.getUTCDay()));
  const ano = quarta.getUTCFullYear();
  const primeiroDeJaneiro = new Date(Date.UTC(ano, 0, 1));
  const primeiraQuarta = new Date(primeiroDeJaneiro);
  primeiraQuarta.setUTCDate(
    primeiroDeJaneiro.getUTCDate()
      + ((3 - primeiroDeJaneiro.getUTCDay() + 7) % 7)
  );
  const semana = Math.floor(
    (quarta.getTime() - primeiraQuarta.getTime()) / (7 * 24 * 60 * 60 * 1000)
  ) + 1;
  return { semana, ano };
}

function parseDate(value: string): Date | null {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(Date.UTC(year, month - 1, day));
}

function atualizarCamposDeData(
  current: PatientData,
  field: "symptomOnsetDate" | "notificationDate",
  value: string
): PatientData {
  const next = { ...current, [field]: value };
  const onset = parseDate(next.symptomOnsetDate);
  const notification = parseDate(next.notificationDate);
  const epi = onset ? calcularSemanaEpi(onset) : null;
  const days = onset && notification && notification >= onset
    ? Math.round(
        (notification.getTime() - onset.getTime()) / (24 * 60 * 60 * 1000)
      )
    : null;

  return {
    ...next,
    symptomEpiWeekNumber: epi ? String(epi.semana) : "",
    symptomEpiYear: epi ? String(epi.ano) : "",
    daysToNotification: days === null ? "" : String(days),
  };
}

// ---------------------------------------------------------------------------
// Hook de autocomplete com debounce
// ---------------------------------------------------------------------------

function useAutocomplete(
  query: string,
  fetchFn: (q: string) => Promise<AutocompleteItem[]>,
  delay = 300
) {
  const [items, setItems] = useState<AutocompleteItem[]>([]);
  const [aberto, setAberto] = useState(false);
  const requestVersion = useRef(0);
  const selectedQuery = useRef<string | null>(null);

  const close = useCallback(() => {
    requestVersion.current += 1;
    setItems([]);
    setAberto(false);
  }, []);

  const queryChanged = useCallback((value: string) => {
    if (value.trim().length < 2) close();
  }, [close]);

  const itemSelected = useCallback((value: string) => {
    selectedQuery.current = value;
    close();
  }, [close]);

  useEffect(() => {
    if (selectedQuery.current === query) {
      selectedQuery.current = null;
      return;
    }
    if (query.trim().length < 2) return;

    const version = requestVersion.current + 1;
    requestVersion.current = version;
    const timer = window.setTimeout(async () => {
      try {
        const resultado = await fetchFn(query);
        if (requestVersion.current !== version) return;
        setItems(resultado);
        setAberto(resultado.length > 0);
      } catch {
        if (requestVersion.current !== version) return;
        setItems([]);
        setAberto(false);
      }
    }, delay);
    return () => {
      window.clearTimeout(timer);
      requestVersion.current += 1;
    };
  }, [delay, fetchFn, query]);

  return {
    items,
    aberto,
    setAberto,
    close,
    queryChanged,
    itemSelected,
  };
}

// ---------------------------------------------------------------------------
// Componente Autocomplete
// ---------------------------------------------------------------------------

type AutocompleteProps = {
  label: string;
  id: string;
  placeholder: string;
  fetchFn: (q: string) => Promise<AutocompleteItem[]>;
  onSelect: (item: AutocompleteItem, label: string) => void;
  onInputChange: (value: string) => void;
  renderLabel?: (item: AutocompleteItem) => string;
  value: string;
};

function Autocomplete({
  label,
  id,
  placeholder,
  fetchFn,
  onSelect,
  onInputChange,
  renderLabel,
  value,
}: AutocompleteProps) {
  const {
    items,
    aberto,
    setAberto,
    close,
    queryChanged,
    itemSelected,
  } = useAutocomplete(value, fetchFn);
  const containerRef = useRef<HTMLDivElement>(null);
  const [focusIndex, setFocusIndex] = useState(-1);
  const listId = `${id}-options`;

  // Fecha ao clicar fora
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close();
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [close]);

  function handleSelect(item: AutocompleteItem) {
    const selectedLabel = renderLabel ? renderLabel(item) : item.name;
    itemSelected(selectedLabel);
    onSelect(item, selectedLabel);
    setFocusIndex(-1);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!aberto) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setFocusIndex(i => Math.min(i + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setFocusIndex(i => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && focusIndex >= 0) { e.preventDefault(); handleSelect(items[focusIndex]); }
    else if (e.key === "Escape") setAberto(false);
  }

  return (
    <div className="autocomplete-wrapper" ref={containerRef}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={aberto}
        aria-controls={listId}
        autoComplete="off"
        placeholder={placeholder}
        value={value}
        onChange={event => {
          queryChanged(event.target.value);
          onInputChange(event.target.value);
          setFocusIndex(-1);
        }}
        onKeyDown={handleKeyDown}
      />
      {aberto && (
        <ul className="autocomplete-list" role="listbox" id={listId}>
          {items.map((item, idx) => (
            <li
              key={item.code}
              role="option"
              aria-selected={idx === focusIndex}
              className={`autocomplete-item${idx === focusIndex ? " focused" : ""}`}
              onMouseDown={() => handleSelect(item)}
            >
              {renderLabel ? renderLabel(item) : item.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function fetchOcupacoes(query: string): Promise<AutocompleteItem[]> {
  const res = await fetch(
    `${API_URL}/api/v1/references/occupations?query=${encodeURIComponent(query)}&limit=10`
  );
  if (!res.ok) return [];
  return (await res.json()).items as AutocompleteItem[];
}

function makeFetchMunicipios(stateCode?: number) {
  return async (query: string): Promise<AutocompleteItem[]> => {
    const params = new URLSearchParams({ query, limit: "20" });
    if (stateCode) params.set("state", String(stateCode));
    const res = await fetch(`${API_URL}/api/v1/references/municipalities?${params}`);
    if (!res.ok) return [];
    return (await res.json()).items as MunicipioItem[];
  };
}

// ---------------------------------------------------------------------------
// PatientForm
// ---------------------------------------------------------------------------

type PatientFormProps = {
  patientData: PatientData;
  setPatientData: React.Dispatch<React.SetStateAction<PatientData>>;
};

function PatientForm({ patientData, setPatientData }: PatientFormProps) {
  const [options, setOptions] = useState<TriageOptions | null>(null);
  const [regioesResidencia, setRegioesResidencia] = useState<RegiaoItem[]>([]);
  const [erroOpcoes, setErroOpcoes] = useState<string | null>(null);

  // Carrega opções da API uma vez
  useEffect(() => {
    const controller = new AbortController();
    async function carregarOpcoes() {
      try {
        const response = await fetch(`${API_URL}/api/v1/triage/options`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`status ${response.status}`);
        const data = await response.json();
        setOptions({
          sexos: data.sexos,
          racas: data.racas,
          escolaridades: data.escolaridades,
          situacoesGestacao: data.situacoesGestacao,
          ufs: data.ufs,
        });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setErroOpcoes(
          "Não foi possível carregar as opções da triagem. Verifique a API."
        );
      }
    }
    void carregarOpcoes();
    return () => controller.abort();
  }, []);

  function set(field: keyof PatientData, value: string) {
    setPatientData(prev => ({ ...prev, [field]: value }));
  }

  async function aoSelecionarMunicipio(
    item: AutocompleteItem,
    selectedLabel: string
  ) {
    const mun = item as MunicipioItem;
    const uf = options?.ufs.find(u => u.code === mun.stateCode);
    setPatientData(prev => ({
      ...prev,
      residenceMunicipality: String(mun.code),
      residenceMunicipalityName: selectedLabel,
      residenceState: mun.stateCode ? String(mun.stateCode) : prev.residenceState,
      residenceStateLabel: uf?.sigla ?? prev.residenceStateLabel,
      residenceHealthRegion: "",
      residenceHealthRegionName: "",
    }));

    try {
      const res = await fetch(
        `${API_URL}/api/v1/references/health-regions?municipality=${mun.code}`
      );
      const data = await res.json();
      const regioes: RegiaoItem[] = data.items ?? [];
      setRegioesResidencia(regioes);
      if (regioes.length === 1) {
        setPatientData(prev => ({
          ...prev,
          residenceHealthRegion: String(regioes[0].code),
          residenceHealthRegionName: regioes[0].name,
        }));
      } else if (regioes.length === 0) {
        setPatientData(prev => ({
          ...prev,
          residenceHealthRegion: "",
          residenceHealthRegionName: "",
        }));
      }
    } catch {
      setRegioesResidencia([]);
    }
  }

  const selectedStateCode = patientData.residenceState
    ? Number(patientData.residenceState)
    : undefined;
  const fetchMunicipios = useMemo(
    () => makeFetchMunicipios(selectedStateCode),
    [selectedStateCode]
  );

  return (
    <section className="patient-form">
      <h2>Dados usados pelo modelo</h2>
      {erroOpcoes && <p role="alert" className="form-error">{erroOpcoes}</p>}

      <div className="form-grid">

        {/* Idade */}
        <div className="form-group">
          <label htmlFor="ageYears">Idade (anos)</label>
          <input
            id="ageYears"
            type="number"
            value={patientData.ageYears}
            onChange={e => set("ageYears", e.target.value)}
            min="0" max="130" step="1"
            placeholder="Ex.: 25"
          />
        </div>

        {/* Sexo */}
        <div className="form-group">
          <label htmlFor="sex">Sexo</label>
          <select id="sex" value={patientData.sex} onChange={e => set("sex", e.target.value)}>
            <option value="">Selecione</option>
            {(options?.sexos ?? []).map(s => (
              <option key={s.code} value={s.code}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Gestação */}
        <div className="form-group">
          <label htmlFor="pregnancyStatus">Situação de gestação</label>
          <select id="pregnancyStatus" value={patientData.pregnancyStatus} onChange={e => set("pregnancyStatus", e.target.value)}>
            <option value="">Selecione</option>
            {(options?.situacoesGestacao ?? []).map(g => (
              <option key={g.code} value={g.code}>{g.name}</option>
            ))}
          </select>
        </div>

        {/* Raça */}
        <div className="form-group">
          <label htmlFor="race">Raça/cor</label>
          <select id="race" value={patientData.race} onChange={e => set("race", e.target.value)}>
            <option value="">Selecione</option>
            {(options?.racas ?? []).map(r => (
              <option key={r.code} value={r.code}>{r.name}</option>
            ))}
          </select>
        </div>

        {/* Escolaridade */}
        <div className="form-group">
          <label htmlFor="educationLevel">Escolaridade</label>
          <select id="educationLevel" value={patientData.educationLevel} onChange={e => set("educationLevel", e.target.value)}>
            <option value="">Selecione</option>
            {(options?.escolaridades ?? []).map(e => (
              <option key={e.code} value={e.code}>{e.name}</option>
            ))}
          </select>
        </div>

        {/* Ocupação: autocomplete */}
        <div className="form-group form-group-wide">
          <Autocomplete
            id="occupationName"
            label="Ocupação"
            placeholder="Digite para buscar (ex: médico, professor...)"
            fetchFn={fetchOcupacoes}
            value={patientData.occupationName}
            onInputChange={value => {
              setPatientData(prev => ({
                ...prev,
                occupationCode: "",
                occupationName: value,
              }));
            }}
            onSelect={(item, selectedLabel) => {
              setPatientData(prev => ({
                ...prev,
                occupationCode: String(item.code),
                occupationName: selectedLabel,
              }));
            }}
          />
          {patientData.occupationCode && (
            <span className="form-hint">CBO: {patientData.occupationCode}</span>
          )}
        </div>

        {/* UF de residência */}
        <div className="form-group">
          <label htmlFor="residenceState">UF de residência</label>
          <select
            id="residenceState"
            value={patientData.residenceState}
            onChange={e => {
              const uf = options?.ufs.find(u => String(u.code) === e.target.value);
              setPatientData(prev => ({
                ...prev,
                residenceState: e.target.value,
                residenceStateLabel: uf?.sigla ?? "",
                residenceMunicipality: "",
                residenceMunicipalityName: "",
                residenceHealthRegion: "",
                residenceHealthRegionName: "",
              }));
              setRegioesResidencia([]);
            }}
          >
            <option value="">Selecione</option>
            {(options?.ufs ?? []).map(uf => (
              <option key={uf.code} value={uf.code}>
                {uf.sigla} ({uf.name})
              </option>
            ))}
          </select>
        </div>

        {/* Município de residência: autocomplete */}
        <div className="form-group form-group-wide">
          <Autocomplete
            key={patientData.residenceState}
            id="residenceMunicipality"
            label="Município de residência"
            placeholder="Digite para buscar (ex: Rio de Janeiro...)"
            fetchFn={fetchMunicipios}
            value={patientData.residenceMunicipalityName}
            onInputChange={value => {
              setPatientData(prev => ({
                ...prev,
                residenceMunicipality: "",
                residenceMunicipalityName: value,
                residenceHealthRegion: "",
                residenceHealthRegionName: "",
              }));
              setRegioesResidencia([]);
            }}
            onSelect={aoSelecionarMunicipio}
            renderLabel={item =>
              item.state ? `${item.name} (${item.state})` : item.name
            }
          />
          {patientData.residenceMunicipality && (
            <span className="form-hint">IBGE: {patientData.residenceMunicipality}</span>
          )}
        </div>

        {/* Região de saúde: preenchida automaticamente ou selecionável. */}
        {regioesResidencia.length > 0 && (
          <div className="form-group form-group-wide">
            <label htmlFor="residenceHealthRegion">Região de saúde</label>
            <select
              id="residenceHealthRegion"
              value={patientData.residenceHealthRegion}
              onChange={event => {
                const selected = regioesResidencia.find(
                  item => String(item.code) === event.target.value
                );
                setPatientData(prev => ({
                  ...prev,
                  residenceHealthRegion: event.target.value,
                  residenceHealthRegionName: selected?.name ?? "",
                }));
              }}
            >
              {regioesResidencia.length > 1 && (
                <option value="">Selecione</option>
              )}
              {regioesResidencia.map(regiao => (
                <option key={regiao.code} value={regiao.code}>
                  {regiao.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Data dos primeiros sintomas */}
        <div className="form-group">
          <label htmlFor="symptomOnsetDate">Data dos primeiros sintomas</label>
          <input
            id="symptomOnsetDate"
            type="date"
            value={patientData.symptomOnsetDate}
            onChange={event =>
              setPatientData(prev =>
                atualizarCamposDeData(
                  prev,
                  "symptomOnsetDate",
                  event.target.value
                )
              )
            }
          />
        </div>

        {/* Data da notificação */}
        <div className="form-group">
          <label htmlFor="notificationDate">Data da notificação</label>
          <input
            id="notificationDate"
            type="date"
            value={patientData.notificationDate}
            onChange={event =>
              setPatientData(prev =>
                atualizarCamposDeData(
                  prev,
                  "notificationDate",
                  event.target.value
                )
              )
            }
          />
        </div>

      </div>
    </section>
  );
}

export default PatientForm;
