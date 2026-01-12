import random

from simulator.config import (
    MinisterConfig,
    GovernmentConfig,
    MPConfig,
    ParliamentConfig,
    JudgeConfig,
    CouncilConfig,
)
from simulator.executive import Government, Minister
from simulator.legislative import MP, Parliament
from simulator.judiciary import Judge, Council

from simulator.adapters import (
    GovernmentAdapter,
    AgentAdapter,
    ParliamentAdapter,
    CouncilAdapter,
)


class MinisterConfigAdapter(AgentAdapter[MinisterConfig, Minister]):
    def convert(self, config: MinisterConfig) -> Minister:
        return Minister(
            id=config.id,
            T_i=config.type,
            P_i=config.party,
            S_i=config.influence,
            W=config.weights,
            o_i=config.opinion,
            o_sup1=config.support1,
            o_sup2=config.support2,
            is_pm=config.is_pm,
        )


class GovernmentConfigAdapter(GovernmentAdapter[GovernmentConfig]):
    def __init__(self):
        self.__minister_adp = MinisterConfigAdapter()

    @classmethod
    def _build_network(
        cls, config: GovernmentConfig, ministers: list[Minister]
    ) -> dict[int, list[int]]:
        ids = [m.id for m in ministers]
        pm = next(m for m in ministers if m.is_pm)
        pm_id = pm.id

        net = {i: set() for i in ids}

        # Prime Minister linked to everyone
        for i in ids:
            if i == pm_id:
                continue
            net[pm_id].add(i)
            net[i].add(pm_id)

        # Other ministers: extra random neighbors up to kgov
        for m in ministers:
            if m.is_pm:
                continue

            current = net[m.id]
            if len(current) >= config.kgov:
                continue

            # only nodes that:
            #   - are not already connected to m
            #   - are not m
            #   - have degree < kgov themselves
            candidates = [
                i
                for i in ids
                if i != m.id and i not in current and len(net[i]) < config.kgov
            ]

            random.shuffle(candidates)

            # compute how many more neighbors m can still take
            max_needed = config.kgov - len(current)
            needed = random.randint(1, max_needed)

            for j in candidates:
                if needed <= 0:
                    break
                net[m.id].add(j)
                net[j].add(m.id)
                needed -= 1

        return {i: list(neigh) for i, neigh in net.items()}

    def convert(self, config: GovernmentConfig) -> Government:
        ministers = list(map(self.__minister_adp.convert, config.ministers))

        return Government(
            ministers=ministers,
            pact=config.pact,
            alpha=config.alpha,
            epsilon=config.epsilon,
            gamma=config.gamma,
            network=self._build_network(config, ministers),
        )


class MPConfigAdapter(AgentAdapter[MPConfig, MP]):
    def convert(self, config: MPConfig) -> MP:
        return MP(
            id=config.id,
            T_i=config.type,  # "MP"
            P_i=config.party,  # "majority" | "opposition" | "independent"
            S_i=config.influence,
            W=config.weights,
            o_i=config.opinion,
            o_sup1=config.support1,
            o_sup2=config.support2,
            is_head=config.is_head,
        )


class ParliamentConfigAdapter(ParliamentAdapter[ParliamentConfig]):
    def __init__(self):
        self.__mp_adp = MPConfigAdapter()

    def convert(self, config: ParliamentConfig) -> Parliament:
        mps = list(map(self.__mp_adp.convert, config.mps))

        parl = Parliament(
            mps=mps,
            n_party=config.n_party,
            n_sits=config.n_sits,
            alpha=config.alpha,
            epsilon=config.epsilon,
            gamma=config.gamma,
        )

        return parl


class JudgeConfigAdapter(AgentAdapter[JudgeConfig, Judge]):
    def convert(self, config: JudgeConfig) -> Judge:
        return Judge(
            id=config.id,
            T_i=config.type,
            P_i=config.party,  # "majority" | "opposition" | "independent"
            S_i=config.influence,
            W=config.weights,
            o_i=config.opinion,
            o_sup1=config.support1,
            o_sup2=config.support2,
            is_president=config.is_president,
        )


class CouncilConfigAdapter(CouncilAdapter[CouncilConfig]):
    def __init__(self):
        self.__judge_adp = JudgeConfigAdapter()

    @classmethod
    def _build_network(cls, judges: list[Judge]) -> dict[int, list[int]]:
        ids = [j.id for j in judges]
        return {i: [j for j in ids if j != i] for i in ids}

    def convert(self, config: CouncilConfig) -> Council:
        judges = list(map(self.__judge_adp.convert, config.judges))

        council = Council(
            judges=judges,
            alpha=config.alpha,
            epsilon=config.epsilon,
            gamma=config.gamma,
            network=self._build_network(judges),
        )

        return council
