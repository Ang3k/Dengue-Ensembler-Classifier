from pathlib import Path
import pandas as pd

class DengueDataCleaner:
    def __init__(self, arquivos=None):
        base = Path(__file__).resolve().parents[1]

        if arquivos is None:
            arquivos = [
                base / "data" / "DENGBR17.parquet",
                base / "data" / "DENGBR18.parquet",
                base / "data" / "DENGBR19.parquet",
            ]
        elif isinstance(arquivos, (str, Path)):
            arquivos = [arquivos]

        self.arquivos = [Path(arquivo) for arquivo in arquivos]
        self.df = self.carregar()

    def carregar(self):
        data_dir = Path(__file__).resolve().parents[1] / "data"
        dfs = []

        for arquivo in self.arquivos:
            if not arquivo.exists() and (data_dir / arquivo.name).exists():
                arquivo = data_dir / arquivo.name

            if arquivo.suffix.lower() == ".csv":
                dfs.append(pd.read_csv(arquivo))
            else:
                dfs.append(pd.read_parquet(arquivo))

        return pd.concat(dfs, ignore_index=True)

    def remover_colunas_iguais(self, df):
        for coluna in list(df.columns):
            if df[coluna].isnull().all():
                df = df.drop(coluna, axis=1)
            elif df[coluna].nunique() == 1:
                df = df.drop(coluna, axis=1)
        return df

    def limpar_angel(self):
        colunas = [
            "ALRM_HEPAT", "COPAISINF", "GRAV_METRO", "COMUNINF", "AUTO_IMUNE",
            "LACO", "PETEQUIAS", "LACO_N", "GRAV_HIPOT", "RENAL", "DOR_RETRO",
            "CLINC_CHIK", "NDUPLIC_N", "CON_FHD", "EVIDENCIA", "ARTRALGIA",
            "CEFALEIA", "GRAV_TAQUI", "ALRM_HEMAT", "SEM_PRI", "GRAV_HEMAT",
            "CLASSI_FIN", "HEMATURA", "RESUL_VI_N", "EXANTEMA", "VOMITO",
            "DT_NASC", "GRAV_PULSO", "CS_RACA", "ALRM_PLAQ", "DT_ALRM",
            "GRAV_SANG", "PLASMATICO", "PETEQUIA_N", "CS_GESTANT", "GRAV_AST",
            "GRAV_ENCH", "GRAV_MIOC", "GRAV_CONV",
        ]

        df = self.df[colunas].copy()

        cols_leakage = [
            "CRITERIO", "DT_ENCERRA", "ALRM_HIPOT", "ALRM_PLAQ", "ALRM_VOM",
            "ALRM_SANG", "ALRM_HEMAT", "ALRM_ABDOM", "ALRM_LETAR", "ALRM_HEPAT",
            "ALRM_LIQ", "DT_ALRM", "GRAV_PULSO", "GRAV_CONV", "GRAV_ENCH",
            "GRAV_INSUF", "GRAV_TAQUI", "GRAV_EXTRE", "GRAV_HIPOT", "GRAV_HEMAT",
            "GRAV_MELEN", "GRAV_METRO", "GRAV_SANG", "GRAV_AST", "GRAV_MIOC",
            "GRAV_CONSC", "GRAV_ORGAO", "DT_GRAV", "COPAISINF", "COMUNINF",
        ]
        df = df.drop(cols_leakage, axis=1, errors="ignore")
        df = self.remover_colunas_iguais(df)

        df["DT_NASC"] = pd.to_datetime(df["DT_NASC"], errors="coerce")
        df["NASC_YEAR"] = df["DT_NASC"].dt.year
        df["AGE"] = 2020 - df["NASC_YEAR"]
        df = df.drop(["DT_NASC", "NASC_YEAR"], axis=1, errors="ignore")

        df = df.drop(["AUTO_IMUNE", "RENAL"], axis=1, errors="ignore")
        df = df.drop(["CS_GESTANT", "CS_RACA", "CLINC_CHIK", "RESUL_VI_N"], axis=1, errors="ignore")

        df["SEM_PRI_YEAR"] = df["SEM_PRI"] // 100
        df["SEM_PRI_WEEK"] = df["SEM_PRI"] % 100
        df = df.drop(columns=["SEM_PRI"])

        df["CLASSI_FIN"] = df["CLASSI_FIN"].map({
            5: 0,
            10: 1,
            11: 1,
            12: 1,
        })
        df = df[df["CLASSI_FIN"].notna()].copy()

        return df

    def limpar_pedro(self):
        colunas = [
            "ID_RG_RESI", "DT_NOTIFIC", "ID_AGRAVO", "DT_ENCERRA", "FEBRE",
            "NU_ANO", "CS_SEXO", "TPAUTOCTO", "HOSPITALIZ", "ID_UNIDADE",
            "ID_OCUPA_N", "NAUSEA", "ID_REGIONA", "SG_UF", "NU_IDADE_N",
        ]

        df = self.df[colunas].copy()

        def parse_idade(valor):
            try:
                s = str(int(valor)).zfill(4)
                unidade = int(s[0])
                numero = int(s[1:])
                if unidade == 4:
                    return numero
                elif unidade == 3:
                    return numero / 12
                elif unidade == 2:
                    return numero / 365
                elif unidade == 1:
                    return numero / 8760
                else:
                    return None
            except:
                return None

        df["IDADE_ANOS"] = df["NU_IDADE_N"].apply(parse_idade)
        df = df.drop(columns=["NU_IDADE_N"])

        df["DT_NOTIFIC"] = pd.to_datetime(df["DT_NOTIFIC"], format="%Y-%m-%d")
        df["MES_NOTIFIC"] = df["DT_NOTIFIC"].dt.month
        df["DIA_NOTIFIC"] = df["DT_NOTIFIC"].dt.day
        df = df.drop(columns=["DT_NOTIFIC"])

        df["DT_ENCERRA"] = pd.to_datetime(df["DT_ENCERRA"], format="%Y-%m-%d")
        df["MES_ENCERRA"] = df["DT_ENCERRA"].dt.month
        df["DIA_ENCERRA"] = df["DT_ENCERRA"].dt.day
        df = df.drop(columns=["DT_ENCERRA"])

        df = df.dropna(subset=["FEBRE", "ID_OCUPA_N", "TPAUTOCTO"])

        return df

    def limpar_ruan(self):
        minhas_colunas = [
            "DT_PCR", "UF", "DT_OBITO", "RESUL_PRNT", "MANI_HEMOR", "ARTRITE",
            "HEMATOLOG", "RES_CHIKS1", "COUFINF", "RESUL_SORO", "MIALGIA",
            "DT_PRNT", "GRAV_ORGAO", "DT_NS1", "DT_INVEST", "ALRM_ABDOM",
            "SG_UF_NOT", "IMUNOH_N", "SOROTIPO", "GRAV_INSUF", "ACIDO_PEPT",
            "CONJUNTVIT", "EPISTAXE", "FLXRECEBI", "DOR_COSTAS", "TP_NOT",
            "ID_MUNICIP", "SEM_NOT", "DT_INTERNA", "HIPERTENSA", "HEPATOPAT",
            "ID_MN_RESI", "ALRM_LIQ", "DT_SIN_PRI", "METRO", "TP_SISTEMA",
            "HISTOPA_N", "CS_ESCOL_N", "GRAV_CONSC",
        ]

        df = self.df[minhas_colunas].copy()

        col = [
            "SOROTIPO", "COUFINF", "DT_NS1", "DT_PCR", "DT_OBITO", "DT_PRNT",
            "RESUL_PRNT", "RES_CHIKS1", "RESUL_SORO", "ALRM_ABDOM", "ALRM_LIQ",
            "GRAV_ORGAO", "GRAV_CONSC", "GRAV_INSUF", "HISTOPA_N", "IMUNOH_N",
        ]
        df = df.drop(columns=col)
        df = self.remover_colunas_iguais(df)

        col = ["HEMATOLOG", "HEPATOPAT", "HIPERTENSA", "ACIDO_PEPT"]
        df = df.drop(columns=col, errors="ignore")

        col = ["DT_INVEST", "DT_INTERNA", "SG_UF_NOT", "TP_NOT"]
        df = df.drop(columns=col)

        return df

    def juntar(self, df_angel, df_pedro, df_ruan):
        df = pd.concat([df_angel, df_pedro, df_ruan], axis=1, join="inner")
        df = df.loc[:, ~df.columns.duplicated()]
        return df.reset_index(drop=True)

    def transformar(self):
        df_angel = self.limpar_angel()
        df_pedro = self.limpar_pedro()
        df_ruan = self.limpar_ruan()
        return self.juntar(df_angel, df_pedro, df_ruan)
