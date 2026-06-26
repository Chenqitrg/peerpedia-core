# 走向共形场论的代数几何基础（修订版）

## ——一份关于 Grothendieck 纲领的私人笔记

---

**日期**：2026-06-26（初稿），修订于同日

**摘要**：本文勾勒一个用纯代数几何方法建立二维共形场论数学基础的纲领。核心论点：
(1) CFT 与数论共享结构 DNA——几何 Langlands 纲领提供了两者之间的精确函子式对应；
(2) Beilinson–Drinfeld 手征代数 + 因子化同调已经提供了「EGA for CFT」的语言基础，但目前缺少关键模块：全（非手征）理论的层论描述、幺正性的几何表述、以及计算性的桥接定理；
(3) 一个完整的纲领需要在五个方向上同时推进——导出共形块、因子化迹的自守性、全 CFT 的 Frobenius 层论、幺正性的 Hodge-理论化、以及对数 CFT 的 Grothendieck–Teichmüller 模空间。

**数学成熟度标注**：本文中，✅ = 已建立的定理；🔶 = 文献中存在部分结果但未完成的进路；❓ = 猜想性但可在当前数学水平上精确表述；💀 = 纯猜想，可能需要尚未发明的数学工具。

---

## 1. 引言：基础在哪里？

### 1.1 有理 CFT 的局部胜利 ✅

二维共形场论的数学基础在 1984 年（BPZ 论文）到 2005 年（Huang 的 Verlinde 猜想证明）之间，对**有理 CFT**（rational CFT）建立了一条逻辑自洽的完整链条：

\[
\text{VOA} \longrightarrow \text{MTC} \longrightarrow
\begin{cases}
\text{手征关联子（Huang–Lepowsky 张量范畴）} \\
\text{全 CFT 关联子（Fuchs–Runkel–Schweigert Frobenius 代数）}
\end{cases}
\]

这条链上的每一步都是定理。在这个意义上，有理 CFT 拥有与「量子力学由 Hilbert 空间 + 自伴算符代数描述」同等严格的数学基础。

然而，这是一个局部胜利。

有理 CFT 是全体 2D CFT 中一个**测度为零**的子集。绝大多数物理上有趣的 CFT——包括 \(c=1\) 紧致化自由玻色子（连续族）、Liouville 理论（连续谱）、渗透模型（\(c=0\)，对数 CFT）、自规避行走（\(c=-2\)，非幺正）——都落在有理 CFT 的范围之外。

### 1.2 手征分裂的崩溃

当前所有进路——VOA 及其推广、模张量范畴、FRS 构造——都依赖于一个可能在一般 CFT 中不成立的假设：**手征分裂**（chiral factorization）。对于对数 CFT，全理论的模空间甚至不等同于左右手征模空间的张量积——存在非分裂的 Jordan 块结构跨越手征分界线。

**数学上精确地说**：设 \(V_L, V_R\) 分别为左右手征 VOA，对应的模范畴为 \(\mathcal{C}_L, \mathcal{C}_R\)。对于有理 CFT，有范畴等价 \(\mathcal{C}_{L} \boxtimes \mathcal{C}_{R} \simeq \mathcal{C}_{\text{full}}\)。对于对数 CFT，左侧的 Deligne 张量积不等价于右侧——存在不可分解的模对象不能写成分裂张量积的形式。这意味着**全 CFT 的模范畴不是左右模范畴的可分张量积范畴**。

### 1.3 四套互不兼容的语言

| 路径 | 核心对象 | 覆盖范围 | 核心限制 |
|---|---|---|---|
| **代数路径**（Huang–Lepowsky–Zhang） | VOA + 张量范畴 | 有理 + 部分非半单 | 对连续谱无处理 |
| **概率路径**（GFF + GMC + SLE） | 高斯自由场 + 随机几何 | Liouville + SLE/LCFT | 仅限特定模型 |
| **算子代数路径**（共形网，Longo–Kawahigashi） | III₁ 型 von Neumann 代数网 | 幺正理论 | 非幺正完全不适用 |
| **因子化代数路径**（Costello–Gwilliam, Beilinson–Drinfeld） | Ran 空间上的 D-模层 | 所有手征 CFT | 缺乏计算工具，非手征情形未完成 |

这四套语言之间的翻译词典严重不完整。例如：概率路径中的 **SLE 的融合规则** ↔ 代数路径中的 **VOA 模的张量积** 仅在少数特例中被建立（如 Virasoro 极小模型 ↔ SLE(κ) 的分类对应）。

### 1.4 我们需要什么？——Grothendieck 类比

这不是诗意的类比；它是一个精确的方法论宣言。

| Grothendieck 之前的代数几何 | 当前的 CFT 数学基础 | 对应的 Grothendieck 解决方案 |
|---|---|---|
| 意大利学派：具体方程+几何直觉 | BPZ + 物理传统：作用量+路径积分 | **相对概形**：不研究单个对象，研究族上的对象 |
| Zariski 拓扑：代数集上的开集拓扑 | VOA + OPE：局部场展开 | **étale 位点/平坦位点**：正确的「局部模型」 |
| Serre FAC (1955)：层论出现但基础仍在复点集 | Huang 2005：VOA 模张量范畴，基础在形式幂级数 | **概形语言**：一切函子化、层论化 |
| Weil 猜想（1949）：深刻的数论-几何连接 | CFT/数论连接（月光、Zhu定理、几何Langlands） | **étale 上同调 + Grothendieck–Lefschetz 迹公式**：统一的框架 |
| **Grothendieck EGA/SGA (1960–69)** | **尚未出现** | —— |

接受这个类比意味着：我们不能仅仅把 CFT 的已有定理翻译成层论语言，也不能满足于用范畴等价重新表述已知结果。**EGA 的价值不在于它重新证明了意大利学派的定理，而在于它使以前不可能的事情成为可能——特别是 étale 上同调和 Weil 猜想的证明。**

CFT 的「Weil 猜想」是什么？我提议是以下几个问题的统一解决：

1. **特征标的模协变性从何而来？**（不仅仅是如何证明，而是从什么结构原理中导出）
2. **为什么 VOA 的分次维数（模形式的 Fourier 系数）是正整数？**（当前没有结构性解释）
3. **对数 CFT 的模空间结构是什么？**（有理 CFT 有 ADE 分类，对数 CFT 有什么？）
4. **共形 bootstrap 为什么有效？**（为什么 crossing 方程的四点函数约束足以确定整个 CFT？这应该有上同调的解释）

---

## 2. CFT 与数论：工具层面 vs. 结构层面

### 2.1 月光：第一条线索 ✅

1978 年 John McKay 注意到：

\[
196884 = 1 + 196883
\]

等式左边是 \(j(\tau) = q^{-1} + 744 + 196884q + \cdots\) 的 Fourier 系数。右边：1（平凡表示维数）+ 196883（Monster 单群的最小非平凡不可约表示维数）。

Conway–Norton（1979）提出了**月光猜想**。Frenkel–Lepowsky–Meurman（1988）构造了**月光模 \(V^\natural\)**——一个顶点算子代数，自同构群 = Monster 单群 \(\mathbb{M}\)。Borcherds（1992）证明了 McKay–Thompson 级数恰好是预测的主模（获 1998 年菲尔兹奖）。

**月光的结构意义**：它建立了第一个精确的函子式连接：

\[
\text{有限群论} \xrightarrow{V^\natural} \text{顶点代数} \xrightarrow{\text{特征标}} \text{模形式/自守形式}
\]

这不是一个「巧合」，而是一个**函子**的三个不同表观。更一般地：

\[
\text{有限群 } G \longrightarrow \text{$G$ 的轨道 VOA } V^G \longrightarrow \text{McKay–Thompson 级数（自守形式）}
\]

### 2.2 Zhu 定理与模不变性的算术化 ✅

Zhu（1996）的定理是 CFT-数论连接的**算术化步骤**：

> **Zhu 定理**：设 \(V\) 为有理、\(C_2\)-余有限 VOA。则不可约模的特征标 \(\chi_M(\tau) = \operatorname{tr}_M q^{L_0 - c/24}\) 组成的向量值函数在 \(\text{SL}(2,\mathbb{Z})\) 作用下按某个有限维表示变换。

**为什么这不仅仅是一个「巧合」**：模群 \(\text{SL}(2,\mathbb{Z})\) 在这里出现，不是因为「我们恰好把他们放在 torus 上」，而是因为：
- \(\text{SL}(2,\mathbb{Z})\) 是亏格 1 曲线的**映射类群**（mapping class group）
- Zhu 的定理等价于说：VOA 特征标组成的向量丛在模叠 \(\overline{\mathcal{M}}_{1,1}\) 上携带一个**平坦联络**（更准确地说，是模叠上的一个局部系统/向量丛与联络）

**数论翻译**：VOA 特征标 ⟷ 同余子群上的向量值模形式。这引出了：

- 模形式的 Fourier 系数是整数 → VOA 的分次维数是整数 ✅
- \(S\)-矩阵的矩阵元是代数数 → 量子维数是 \(\mathbb{Q}(e^{2\pi i / \kappa})\) 中的代数整数 🔶（已知对有理 CFT，需要证明对一般 VOA）
- Verlinde 公式 \(N_{ab}^c = \sum_d \frac{S_{ad} S_{bd} S_{cd}}{S_{0d}}\) 保证融合系数是非负整数 ✅

**与数论模式的平行**：

\[
\text{模形式} \longrightarrow \text{Galois 表示} \longrightarrow L\text{-函数} \longrightarrow \text{特殊值} \longrightarrow \text{代数性定理}
\]

\[
\text{VOA 分次维数} \longrightarrow \text{映射类群表示} \longrightarrow \text{特征标} \longrightarrow \text{Verlinde 公式} \longrightarrow \text{融合规则}
\]

### 2.3 几何 Langlands：最深层的结构连接 ✅/🔶

这是本文最核心的数学主张。我们在此给出比初稿更精确的表述。

**经典 Langlands 纲领**（1967–）：数域的 Galois 表示 ↔ 自守表示。

\[
\text{Gal}(\overline{\mathbb{Q}}/\mathbb{Q}) \text{ 的 \(n\) 维表示} \longleftrightarrow \text{GL}_n(\mathbb{A}_{\mathbb{Q}}) \text{ 上的自守表示}
\]

**函数域 Langlands**（Drinfeld 1974, Lafforgue 2002）：将 \(\mathbb{Q}\) 替换为 \(\mathbb{F}_q(X)\)。此时：
- Galois 侧 → 曲线 \(X\) 的 étale 基本群
- 自守侧 → \(\text{Bun}_G(X)\) 上的函数（\(\ell\)-adic 层）

**几何 Langlands**（Beilinson–Drinfeld 1990s–）：将 \(\mathbb{F}_q\) 替换为 \(\mathbb{C}\)，将 \(\ell\)-adic 层替换为 D-模：

\[
D\text{-模}(\text{Bun}_G(X)) \longleftrightarrow \text{QCoh}(\text{Loc}_{G^L}(X))
\]

**CFT 的精确角色** ✅：

> **定理（Feigin–Frenkel 1990, Beilinson–Drinfeld 2004）**：WZW 模型在临界 level \(k = -h^\vee\) 的共形块恰好是几何 Langlands 的 Hecke 特征 D-模。

具体来说，在曲线 \(X\) 上的仿射 Kac–Moody 代数 \(\hat{\mathfrak{g}}\) 的 level \(k\) 表示中：

- **非临界 level**（\(k \neq -h^\vee\)）：模范畴等价于量子群 \(U_q(\mathfrak{g})\) 的表示范畴（Kazhdan–Lusztig 等价）
- **临界 level**（\(k = -h^\vee\)）：模范畴出现剧烈变化——中心变成无穷大的可交换代数（Feigin–Frenkel 中心），模的全局截面恰好是 \(\text{Bun}_G(X)\) 上的 Hecke 特征 D-模

精确的函子式对应：

\[
\begin{aligned}
\text{WZW 共形块} &\xrightarrow{\sim} \text{Hecke 特征 D-模} \\
\text{共形块空间} &\xrightarrow{\sim} \text{仿射 Grassmannian 上 critical level 模的全局截面} \\
\text{BPZ 方程} &\xrightarrow{\sim} \text{Hecke 特征条件} \\
\text{OPE 结合性} &\xrightarrow{\sim} \textbf{geometric Satake 等价} \\
\text{融合规则} &\xrightarrow{\sim} \text{geometric Satake 中的张量积} \\
\text{模不变性} &\xrightarrow{\sim} \text{Hitchin 联络（共形块丛上的平坦联络）}
\end{aligned}
\]

**Geometric Satake 等价**（Mirković–Vilonen, Ginzburg, Beilinson–Drinfeld）✅：这是OPE结合性在几何Langlands中的精确对应物：

\[
\text{Rep}(G^L) \simeq \text{Perv}_{\text{GO}}(\text{Gr}_G)
\]

左侧是对偶群 \(G^L\) 的有限维表示（融合规则的来源），右侧是仿射 Grassmannian \(\text{Gr}_G\) 上的 GO-等变 perverse 层。

这意味着：**融合规则不是 CFT 的偶然性质——它是 geometric Satake 等价在物理层面的表观。**

**核心结论** ✅：CFT 与数论的关系不是「使用模形式作为工具」。两者是**同一结构在复曲线和数域两个不同基底上的表观**：

\[
\begin{array}{ccc}
\text{数域 } \mathbb{Q} & \longleftrightarrow & \text{复曲线 } X/\mathbb{C} \\
\text{Galois 群 } \text{Gal}(\overline{\mathbb{Q}}/\mathbb{Q}) & \longleftrightarrow & \text{映射类群 } \Gamma_{g,n} \\
\text{自守表示} & \longleftrightarrow & \text{D-模/手征代数} \\
\text{L-函数} & \longleftrightarrow & \text{共形块 + 特征标} \\
\text{Frobenius 迹公式} & \longleftrightarrow & \text{Verlinde 公式（？）} \\
\text{类域论} & \longleftrightarrow & \text{有理 CFT 的 ADE 分类} \\
\text{非 Abel 类域论（Langlands）} & \longleftrightarrow & \text{一般 CFT 的分类} \\
\end{array}
\]

最后的两个「（？）」是目前数学中最深层的未解决问题。

---

## 3. Grothendieck 进路：Segal 公理、手征代数、因子化同调

### 3.1 Segal 的函子 CFT ✅/🔶

Graeme Segal 的想法：**CFT 是一个函子**。

设范畴 \(\mathcal{C}\)：
- **对象**：\(S^1\) 的有限多个拷贝（参数化的边界圈）
- **态射**：带参数化边界的 Riemann 面（配边）
- **合成**：边界的缝合
- **对称幺半结构**：不交并

则一个 CFT 是函子：

\[
Z: \mathcal{C} \longrightarrow \text{Hilb}
\]

满足：(1) 幺半性；(2) 共形映射下协变；(3) 缝合对应算符的迹。

**这个框架的力量**：它将 CFT 定义为**范畴之间的函子**——这是真正的 Grothendieck 式定义（用态射的性质而非对象的内部构造来定义结构）。

**数学上的三个精确问题** 🔶：

1. **高亏格的模不变性**：Segal 在亏格 0 和 1 上等价于标准 CFT 定义。但在高亏格，他需要手工加上模不变性条件——这暗示 Segal 的范畴 \(\mathcal{C}\) 缺少某种「高同伦结构」（可能是 A∞/E∞ 结构），使得模不变性可以从缝合公理中自动导出。

2. **非有理 CFT 的迹条件崩溃**：对于连续表示谱，Hilbert 空间的张量积上不一定存在迹（需要核型算子条件）。Segal 框架没有处理这个分析性困难——它假装所有 Hilbert 空间的张量积都带有良好定义的迹。对于对数 CFT，在非半单状态下 Segal 的缝合结构没有良好的定义。

3. **与 cobordism hypothesis 的关系**：Lurie 2009 证明了 fully extended TFT ↔ fully dualizable objects。CFT 不是 fully extended TFT——共形结构打破了拓扑不变性。但 CFT 应该是某种「anomalous TFT」（带反常的 TFT，反常由中心荷 \(c\) 给出）。这个精确表述尚未被建立。

### 3.2 Beilinson–Drinfeld 手征代数 ✅

Beilinson–Drinfeld（*Chiral Algebras*, 2004）的手征代数理论是目前最接近 Grothendieck 式 CFT 基础的进路。它提供了手征（holomorphic）CFT 的完全代数几何化。

#### 3.2.1 Ran 空间

BD 框架的基础对象：

\[
\operatorname{Ran}(X) = \{ X \text{ 的所有有限非空子集} \}
\]

**为什么需要 Ran 空间？** 传统的局部量子场论中，「局部性」意味着场在空间分离的点上独立。CFT 的 OPE 恰恰相反——场在点**重合**时有非平凡的极限行为。Ran 空间的位点结构将「点分离」和「点重合」统一处理为一个层论框架：

- **开集**：\(\{S \subset X_{\text{finite}} : S \cap U_i \neq \emptyset \text{ 对某开覆盖 } U_i\}\)
- **重合对角线**：Ran 空间的对角线 \(\Delta: X \hookrightarrow \operatorname{Ran}(X)\) 是层的特殊化/限制的自然场所

这完全平行于 Grothendieck 的洞见：代数几何的「局部模型」不是开集，而是交换环的谱。CFT 的「局部模型」不是时空区域，而是曲线上的**形式邻域**，其「代数」是顶点代数。

#### 3.2.2 手征代数的定义 ✅

> **手征代数** \(\mathcal{A}\) 是 Ran 空间上的一个 D-模层（或拟凝聚层），配备一个因子化同构：
> \[
> \mathcal{A}(I \sqcup J) \xrightarrow{\sim} \mathcal{A}(I) \boxtimes \mathcal{A}(J)
> \]
> 其中 \(I, J\) 是 \(X\) 的互不相交的有限子集。

这个「因子化结构」**恰好编码了 CFT 的 OPE**：点分离时，层的行为是张量积；点重合时，通过特殊化函子获得 OPE 展开。

#### 3.2.3 核心定理 ✅

> **BD 等价定理**：在光滑复代数曲线 \(X\) 上，存在范畴等价：
> \[
> \{\text{\(X\) 上的手征代数}\} \longleftrightarrow \{\text{顶点代数} + \text{\(X\) 上的形式邻域数据}\}
> \]

换句话说：**顶点代数 = 手征代数的局部截面**。就像：
- 交换环 = 仿射概形的全局截面
- 李代数 = 形式群的无穷小结构
- Hopf 代数 = 仿射群概形的函数环

这完成了 Grothendieck 纲领的第一步：**将 CFT 从「平面 \(\mathbb{C}\) 上的代数结构」几何化为「任意复曲线 \(X\) 上的全局对象」。**

#### 3.2.4 BD 框架中已建立的内容 ✅

| 标准 CFT 概念 | 手征代数翻译 | 状态 |
|---|---|---|
| 顶点代数 \(V\) | Ran 空间上的手征代数层 | ✅ 定理 |
| 真空态 | 层的单位截面 | ✅ 定义 |
| 保形向量 | 从 Virasoro 代数的普遍包络代数的态射 | ✅ 定义 |
| 共形块（亏格 0） | Ran 空间上的 de Rham 上同调 | ✅ 定理 |
| 融合规则（亏格 0） | Ran 空间上的特殊化函子的 monodromy | ✅ 定理 |
| 模不变性（亏格 1） | 模叠上手征代数的下降条件 | 🔶 部分 |
| 高亏格共形块 | 曲线上手征代数的因子化同调 | 🔶 部分 |
| Hecke 特征层 | 临界 level 手征代数的模 | ✅ 定理 |
| 共形块上的 Hitchin 联络 | Gauss–Manin 联络（相对 de Rham 上同调） | ✅ 定理 |

#### 3.2.5 仍然缺失的内容

**1. 非手征（全）理论** 💀

BD 框架主要处理手征 CFT。全理论需要左右交换手征代数的某种组合——这在代数几何中没有现成的对应物。可能的方向：

- **实代数几何路径**：考虑 \(X\) 的实形式（如 \(\mathbb{CP}^1\) 的赤道 \(S^1\)），上面定义一个「实因子化层」。问题：代数几何的工具（D-模、de Rham 上同调）在实代数几何中没有自然的对应物。
- **复共轭对路径**：将全 CFT 定义为 \((X, \bar{X})\) 上的一个「双重手征代数」，左右分量在某种反全纯对合下交换。这个进路的困难是：\(X\) 和 \(\bar{X}\) 是不同复结构下的同一实曲面——它们的 Ran 空间之间的关系不是代数态射。
- **因子化代数的 Costello–Gwilliam 进路**：Costello–Gwilliam 的因子化代数定义在光滑流形上（不限于复曲线），可能更适合处理非手征理论。但目前 Costello–Gwilliam 框架与 BD 框架之间的精确关系仅在特定例子中被建立。

**2. 幺正性条件** 💀

如何在代数几何框架中内建幺正性？共形网进路中，幺正性内置于 III₁ 型因子的模理论——正性从 von Neumann 代数的 Tomita–Takesaki 理论自然而来。代数几何目前完全缺少对应的结构。

可能的方向：
- **Hodge 结构/极化**：复几何中，正性通过 Kähler 度量和 Hodge 结构形式化。幺正 CFT 可能对应于某种 **polarized 手征代数**——手征代数 + 因子化同调上的一个 Hermitian 正定形式。
- **反射正性**（Osterwalder–Schrader）：欧几里得 QFT ⟷ 相对论 QFT 的关键桥梁。反射正性在代数几何中的翻译可能涉及某种 **hermitian 范畴**或 ***-结构**。
- **\(\mathbb{F}_1\) 猜想版本**（见第 5 节）：幺正性 = Hodge 结构是**纯的**（即权过滤退化为一个权）。非幺正 CFT = 混合 Hodge 结构。

**3. 对数/非半单理论** 🔶

\(C_2\)-余有限条件在 BD 框架中对应什么？非 \(C_2\)-余有限手征代数的 Ran 空间行为完全不清楚。具体的技术障碍：

- 在有理 CFT 中，模范畴是半单的 → 共形块空间是有限维 → de Rham 上同调是有限维 → D-模是 holonomic。
- 在对数 CFT 中，模范畴是非半单的 → 共形块可能是无穷维的（或更需要导出版本）→ de Rham 上同调需要导出范畴的框架（Gaitsgory–Rozenblyum 的 IndCoh 进路）。

### 3.3 因子化同调：拓扑不变量的函子式计算 🔶

**因子化同调**（Ayala–Francis–Tanaka 2017–）是 CFT 基础过去十年最重要的新工具。

**核心构造**：给定一个 \(n\)-碟片代数（\(E_n\)-algebra）\(\mathcal{A}\) 和一个带框架的 \(n\)-流形 \(M\)：

\[
\int_M \mathcal{A} \in \text{Ch} \quad \text{（链复形/导出范畴）}
\]

**对于 CFT**：顶点代数 \(V\) 是一个 \(\mathbb{R}^2\)-碟片代数（\(E_2\)-代数）。对于 Riemann 面 \(\Sigma\)，

\[
\int_\Sigma V
\]

自动复现**共形块空间**（通过取同调）。

**因式化同调的三个关键优势**：

1. **不需要坐标**：传统 CFT 中，共形块的构造依赖局部坐标（Virasoro 生成元用 \(z, \bar{z}\) 表示），高亏格时需要拼贴坐标卡。因子化同调只依赖于 \(V\) 的代数结构和 \(\Sigma\) 的拓扑/几何，不需要坐标选择。这使得模不变性成为**自动的**——不同坐标选择对应 \(\Sigma\) 的不同分解，而因子化同调对分解协变。

2. **自然推广到非半单情形** 🔶：因子化同调在非半单情况下仍然是定义良好的导出函子。这使得「对数 CFT 的导出版本共形块」可以被自然地定义为导出对象——传统方法中构造这些东西极其困难。具体地说：

   - 若 \(V\) 是 \(C_2\)-余有限的 → \(\int_\Sigma V\) 的**同调**（非导出对象）是有限维的 → 传统共形块空间
   - 若 \(V\) 不是 \(C_2\)-余有限的 → 必须保留整个链复形 \(\int_\Sigma V\) → **导出共形块**

3. **特征标公式的函子化**：经典的 VOA 特征标 \(\chi_M(\tau) = \operatorname{tr}_M q^{L_0 - c/24}\) 在因子化同调语言中是：

   \[
   \operatorname{Tr}^{\text{fact}}\left( \int_{T^2_\tau} V \right)
   \]

   即 torus 上因子化同调的某种分次迹。这暗示模不变性（在 \(S: \tau \mapsto -1/\tau\) 下的协变性）应该能从因子化同调的函子性中**自动导出**——当前模不变性作为「手工条件」强加于特征标上，但在因子化同调框架中，torus 的不同标记（\(a\)-圈与 \(b\)-圈的交换）对应着曲面分解的不同方式。

**关键限制**：因子化同调目前主要是**拓扑**工具——它对流形的光滑结构敏感，但对共形结构不敏感。真正的 CFT 需要**共形**结构，而不仅仅是拓扑/光滑结构。将这从拓扑升级到共形几何是当前框架中的一个关键缺口。

具体地说：\(\int_\Sigma V\) 作为链复形只依赖于 \(\Sigma\) 的**拓扑 + 光滑结构**。要从中提取依赖于共形结构的数据（如 torus 配分函数 \(Z(\tau)\) 对模参数 \(\tau\) 的依赖性），需要额外的结构——可能是因子化同调上的某种 **Hodge 结构**或 **共形结构**。

### 3.4 导出代数几何中的手征代数（Gaitsgory–Rozenblyum） 🔶

初稿中遗漏了这个重要的技术发展。Gaitsgory–Rozenblyum 的 *A Study in Derived Algebraic Geometry*（2017）在导出代数几何框架中系统重写了手征代数理论。

**关键差异**：
- BD 框架：手征代数 = Ran 空间上的 D-模层（abelian 范畴）
- GR 框架：手征代数 = Ran 空间上的 **IndCoh** 层（导出范畴）

升级为导出范畴不是技术细节——它对非半单 CFT（对数 CFT）至关重要：
- 在 abelian 设置中，非半单意味着某些自然的函子（如对偶）不是正合的
- 在导出设置中，非半单被自动处理——导出版本的对偶、迹、上同调都是定义良好的

特别地，GR 的「导出手征代数」可能提供对数 CFT 的精确数学框架——使得目前仅被非严格地研究的 triplet \(W_p\) 模型、symplectic 费米子等可以被严格地形式化为导出对象。

---

## 4. 设想中的「EGA for CFT」：一个纲领

以下纲领将 BD/GR 框架、因子化同调、几何 Langlands 统一为四个概念性卷。这不是目录，而是一组**问题群**——每卷以一两个核心定理/猜想为中心，周围的定义和中间结果服务于它们。

### 卷 0：CFT 的相对视角

**核心原则**：不研究孤立的 CFT，而研究 CFT 在基曲线**族**上的行为。

在 Grothendieck 的代数几何中，我们不研究「一个代数簇 \(X\)」，而是研究态射 \(f: X \to S\)。这允许基变换、平滑态射的性质、上同调的基变换定理。

**CFT 的相对版本**：

> 给定一族光滑曲线 \(\pi: \mathcal{X} \to S\)，一个**相对 CFT** 是 \(\operatorname{Ran}(\mathcal{X}/S)\) 上的一个手征代数（或手征代数层），满足基 \(S\) 上的平坦性条件。

**这为什么重要——一个具体的例子**：

设 \(\mathcal{M}_g\) 为亏格 \(g\) 曲线的模叠，\(\pi: \mathcal{C}_g \to \mathcal{M}_g\) 为普遍曲线。则一个 CFT（更准确地说，一个手征代数 \(V\)）定义一个相对 CFT，使得：

- 在每条纤维 \(\mathcal{C}_s\) 上，共形块空间是 \(\int_{\mathcal{C}_s} V\)（因子化同调）
- 在模叠 \(\mathcal{M}_g\) 上，这些共形块空间形成一个**向量丛**（共形块丛/vector bundle of conformal blocks）
- 这个向量丛上的**平坦联络** = Hitchin 联络 = **Gauss–Manin 联络**在相对 de Rham 上同调上的表观

**关键定理**（TUY 1988, Hitchin 1990）✅：共形块丛在 \(\mathcal{M}_g\) 上的 Hitchin 联络是平坦的。**但 TUY 的证明使用了具体的代数构造（KZ 联络的推广 + VOA 的表示论计算）。**

**卷 0 的核心目标**：用纯相对因子化同调的语言重写这个证明。具体地说：证明 \(\int_{\mathcal{X}/S} V\)（在导出范畴中）携带一个自然的 Gauss–Manin 联络，该联络的平坦性来自 de Rham 上同调的基变换性质。TUY–Hitchin 的定理应该是这个一般性原理的一个推论——而不需要一个独立的、基于 VOA 表示论计算的证明。

**第二个核心目标** 🔶：通过基变换研究**退化**。将一族平滑曲线退化到一个节点曲线 \(X_0\)。CFT 的极限行为（factorization limit）应该由手征代数的某种**特殊化**给出。这是用代数几何严格处理 CFT 的**边界行为**（boundary CFT，defect CFT）的自然框架。

### 卷 I：CFT 的「拓扑」——因子化位点

**内容**：
- Ran 位点与 Ran 空间的拓扑斯理论：基础定义、Grothendieck 拓扑、层的范畴
- 因子化层：定义、基本性质、因子化结构的公理
- **核心定理** ✅：顶点代数 ⟷ Ran 空间上具有曲率自由的因子化 D-模层（BD 等价定理的重述）
- 因子化位点上的拟凝聚层、D-模、perverse 层
- 因子化层沿闭嵌入的拉回和特殊化

**卷 I 的新内容（相对于 BD）**：

1. **非局域因式化层**：BD 的因子化结构基于「分离点 → 张量积」。但对于非手征/全 CFT，我们需要的是某种「非局域因子化」——保留了分离点上的某种交叉数据。

2. **层论的融合**：将 Huang–Lepowsky 的**融合张量积**重新表述为因子化位点上的**层论融合**。具体地说，VOA 模的融合 = Ran 空间中沿重合对角线的特殊化函子。这应该给出 Huang–Lepowsky 的顶点张量范畴构造的一个纯层论证明。

3. **p-进对应**：Scholze 的 diamonds/p-进 Hodge 理论中，Ran 空间和因子化层的 p-进类似物正在出现（Fargues–Scholze 的几何 Langlands 纲领）。卷 I 应该为 \(\mathbb{C}\) 和 p-进情形提供一个统一的语言。

### 卷 II：CFT 的「同调」——因子化同调

**内容**：
- 因子化同调的严格定义：\(\int_\Sigma: \text{Alg}^{\text{Fact}}(\text{Ran}_X) \to \text{Ch}\)
- **核心定理 1** ✅：对于 \(C_2\)-余有限手征代数，\(\int_\Sigma V\) 是有限维链复形，同调 ≃ 传统共形块空间
- **核心定理 2** 🔶：因子化 Künneth 公式——缝合 ⟺ 因子化同调的张量积
- **核心定理 3**（❓猜想）：非半单情形——导出共形块的定义、Euler 示性数公式
- **关键应用** ✅：映射类群在 \(\int_\Sigma V\) 上的作用（因子化同调的拓扑不变性 ⇒ 映射类群表示）

**卷 II 的最关键技术问题** 🔶：因子化同调目前只对流形的拓扑/光滑结构敏感。要获得 CFT（而非 TFT），需要将**共形结构**的信息编码进因子化同调中。可能的方法：

- 将 Riemann 面 \(\Sigma\) 的复结构视为因子化代数上的一个 **action**（某种 operad 作用）
- 或定义一个新的「共形因子化同调」——不是对流形不变，而是对**共形等价类**不变

### 卷 III：CFT 的「上同调」——特征标与自守性

**内容**：
- 因子化迹 \(\operatorname{Tr}^{\text{fact}}: K_0(\text{FactAlg}) \to \text{ModForms}\)
- **核心猜想**（❓）：Torus 上因子化同调的迹自动满足模协变性
- 因子化迹 → 模叠上的局部系统 → 特征标 → 向量值模形式
- Verlinde 公式作为因子化迹的分解定理
- 特征标的 Galois 性质：\(S\)-矩阵的矩阵元是代数整数

**初稿的一个关键过度声称需要在此修正**：

初稿声称「模协变性应该从因子化同调的函子性中**自动导出**」。实际上，Zhu 定理的模协变性依赖于：
1. VOA 的 \(C_2\)-余有限条件（保证有限维性）
2. \(L_0\) 的对角化性质（从 Virasoro 代数的表示论）
3. 零模的有限性

这些是**分析性**输入，而非纯同调论的性质。因子化同调框架目前**没有取代这些输入**——它提供的是这些输入一旦满足时，模协变性的**函子性表述**。

**精确化**：卷 III 的目标不是「证明 Zhu 定理不需要计算」，而是「将 Zhu 定理升级为某种因子化层在模叠上的下降定理」。等价于说：

> Torus 上因子化同调 \(\int_{T^2} V\) 作为 \(\text{SL}(2,\mathbb{Z})\)-模的表示是 \(\mathcal{M}_{1,1}\) 上某个局部系统的纤维。

**如果成功**：这会在范畴层面揭示模不变性的起源——它不是计算的产物，而是因子化同调对曲面分解方式协变的必然结果。

### 卷 IV：CFT 的「Galois 理论」——分类的范畴层级

**修订后的分类对应表**（修正了初稿的错误）：

| CFT 类型 | 表示范畴的数学性质 | 类比于 | 精确程度 |
|---|---|---|---|
| 有理（幺正）CFT | 半单模张量范畴 + 非退化辫子 + 模不变性 | 有限 étale 覆盖的 Galois 范畴 | ✅ 严格（Huang 2005） |
| 有理（非幺正）CFT | 半单模张量范畴（辫子可能退化） | 有限 Galois 模的范畴 | 🔶 部分已知 |
| 对数 CFT | 有限非半单辫子张量范畴（Jordan–Hölder 有限） | p-进 Galois 表示的非半单约化 | 🔶 正在发展（Hofer–Runkel 2025） |
| 连续谱 CFT（\(c \ge 1\)） | 无穷多简单对象 + 连续参数族 | 正特征代数群的特征标簇 | ❓ 猜想 |
| 一般 CFT | 某类导出辫子∞-范畴 | Grothendieck–Teichmüller 的∞-范畴表示（？） | ❓ 猜想 |

**核心猜想修订**（❓）：

> 设 \(X\) 为 \(\mathbb{C}\) 上亏格 \(g\) 的光滑射影曲线。存在函子：
> \[
> \Phi: \{\text{\(X\) 上的 \(C_2\)-余有限手征代数}\} \longrightarrow \{\pi_1^{\text{orb}}(\mathcal{M}_{g,n}) \text{ 的有限维射影表示}\}
> \]
> 其中 \(\pi_1^{\text{orb}}\) 是轨道基本群（作用在整个模叠上）。TUY/Hitchin 证明了 \(\Phi\) 是定义良好的。猜想：\(\Phi\) 是**忠实**的（不同的 CFT 给出不同构的表示），在适当的附加条件下甚至是**满**的（每个映射类群的射影表示来自某个 CFT）。

**为什么满性如此困难**：不是每个映射类群的表示都会来自于 CFT——你需要表示满足某种**局部性条件**（缝合公理、因子化性质）。这等价于：映射类群的表示必须来自某个**局部系统**在模叠上的限制，该局部系统满足某个平坦性条件。

---

## 5. \(\mathbb{F}_1\) 视角：一个精确化尝试

初稿的 \(\mathbb{F}_1\) 猜想是富有启发性但缺乏精确性的。这里给出一个可以逐步精确化的版本。

### 5.1 \(\mathbb{F}_1\)-几何的当前状态 🔶

「一元域」\(\mathbb{F}_1\) 上的几何有几个相互竞争的提案：
- **Soulé 2004**：有限集合上的代数几何
- **Connes–Consani 2010**：幺半群上的几何
- **Toën–Vaquié**：导出进路
- **Borger**：\(\lambda\)-环（\(\Lambda\)-结构）

目前没有共识哪个是正确的，但核心直觉是一致的：\(\mathbb{Z}\) 上的几何对象的某种「组合极限」应该对应 \(\mathbb{F}_1\) 上的几何对象。

### 5.2 CFT ⟷ \(\mathbb{F}_1\)：三层精确化

**Layer 1（最具体的）** 🔶：VOA 的分次维数的**正整性**。

VOA \(V = \bigoplus_{n \ge 0} V_n\) 的分次维数 \(\dim V_n\) 是正整数。这些正整数是模形式 Fourier 系数的组成部分。在计数几何中，**正整数来自计数**——给定 \(\mathbb{F}_q\) 上的代数簇 \(X\)，\(\#X(\mathbb{F}_q)\) 是正整数。

**精确猜想 A**：存在一个「\(\mathbb{F}_1\) 上的对象」\(\mathcal{X}_V\)（其精确性质有待定义），使得：
\[
\dim V_n = \text{rk}_{\mathbb{F}_1} H^0(\mathcal{X}_V, \mathcal{L}^{\otimes n})
\]
其中「\(\text{rk}_{\mathbb{F}_1}\)」是某种组合秩函数（可能是集合的势，或 \(\lambda\)-环的秩）。

这会给 \(\dim V_n\) 的正整性提供一个结构性原因，而非「它们恰好是模形式的 Fourier 系数」。

**Layer 2（中间层）** ❓：融合规则 = \(\mathbb{F}_1\) 上的交理论。

有理 CFT 的融合规则 \(N_{ab}^c\) 是非负整数（模张量范畴结构常数）。这强烈暗示它们是某种**计数**：

**精确猜想 B**：存在一个 \(\mathbb{F}_1\)-位点 \(\text{Bun}_{G^L}(\mathbb{F}_1)\) 和一个交配对，使得：
\[
N_{ab}^c = \langle \mathcal{F}_a \cdot \mathcal{F}_b, \mathcal{F}_c \rangle_{\mathbb{F}_1}
\]
其中 \(\mathcal{F}_a\) 是 \(\text{Bun}_{G^L}(\mathbb{F}_1)\) 上的某种「\(\mathbb{F}_1\)-层」。

**线索**：Geometric Satake 等价 \(N_{ab}^c = \dim \operatorname{Hom}_{G^L}(V_a \otimes V_b, V_c)\) 已经将融合系数表达为表示范畴中的维数。如果 \(G^L\) 的表示范畴本身是某个 \(\mathbb{F}_1\)-对象的 \(\ell\)-adic 实现（即某种 quantum group at root of unity = \(\mathbb{F}_1\)-对象的 Hodge 实现），那么融合规则的起源就被还原为 \(\mathbb{F}_1\) 上的计数。

**Layer 3（最深层的）** 💀：完整的 \(\mathbb{F}_1\)-对应。

> CFT 是 \(\mathbb{F}_1\) 上的某种**上同调理论**在 \(\mathbb{C}\) 上的**Hodge 实现**。

这意味着存在以下结构图：

\[
\begin{array}{ccccc}
&\mathbb{F}_1\text{-motif } M_V && \xrightarrow{\text{Hodge 实现}}& \text{CFT } V\\
&\downarrow{\text{点计数}} && &\downarrow{\text{特征标}}\\
&\text{正整数（组合数）} && \xrightarrow{\text{识别}}& \text{模形式 Fourier 系数}
\end{array}
\]

**为什么这不算荒谬**：已有以下平行现象：
- \(\mathbb{F}_q\) 上的点计数 → Weil 猜想 → 复上同调的 Frobenius 迹 → 代数整数性
- \(\mathbb{F}_1\) 上的「点计数」 → ??? → 复上同调的某种迹 → VOA 分次维数的正整性

如果 \(\mathbb{F}_1\)-Hodge 理论存在，它将把模形式（CFT 特征标）识别为 \(\mathbb{F}_1\)-motif 的 Hodge 实现，就像经典 Hodge 理论将代数簇的上同调识别为带有 Hodge 结构的向量空间。

**当前最接近 \(\mathbb{F}_1\)-CFT 对应的工作** 🔶：
- Behrend–Bryan–Szendrői 的 motivic Hall 代数（计算 3-CY 范畴上的计数不变量 → 生成顶点代数结构）
- Joyce 的 vertex algebra structure on homology of moduli stacks
- 这暗示：**顶点代数结构可以从计数几何中（motivically）产生**——这恰好是 \(\mathbb{F}_1\)-猜想所预测的。

### 5.3 幺正性的 \(\mathbb{F}_1\) 解释 💀

**猜想 C**（最危险但也最有趣的）：
- 幺正 CFT ⟷ \(\mathbb{F}_1\) 上的**纯 Hodge 结构**（权过滤是退化的）
- 非幺正 CFT ⟷ \(\mathbb{F}_1\) 上的**混合 Hodge 结构**（非退化权过滤）

如果成立，幺正性的起源将被还原为「权的纯性」——一个数论和代数几何中已经深入理解的概念。

---

## 6. 当前的技术前沿与具体的下一步

### 6.1 导出共形块与非半单情形 🔶

**具体问题**：定义 triplet \(W_p\) 代数（对数 CFT 的经典例子）在任意亏格 \(g \ge 1\) 的 Riemann 面上的**导出共形块**，计算其 Euler 示性数，验证它们在形变下的不变性。

**当前工具**：
- **因子化同调**（Ayala–Francis–Tanaka）：提供导出共形块的基础定义
- **导出代数几何**（Gaitsgory–Rozenblyum）：提供 IndCoh 层的技术框架
- **Hofer–Runkel 2025**：最近的 TFT 对应（非半单 CFT/TFT 对应，arXiv:2511.21231）提供了低亏格的分类工具

**可能的技术路径**：
1. 将 \(W_p\) 代数实现为某个超手征代数（super chiral algebra）的表示
2. 在 Ran 空间上构造对应的导出因子化层
3. 使用 GR 框架中的 IndCoh 上同调定义导出共形块
4. 计算低亏格（\(g=0,1\)）并验证与已知结果一致
5. 建立 Euler 示性数的因子化公式（通过导出 Künneth）

### 6.2 因子化迹与模协变性 ❓

**精确版本**：设 \(V\) 为 \(C_2\)-余有限手征代数。构造因子化同调 \(\int_{T^2_\tau} V\) 上的一个**迹映射**，使得：

\[
\operatorname{Tr}^{\text{fact}}: K_0\left(\text{Perf}\left(\int_{T^2_\tau} V\right)\right) \longrightarrow \mathbb{C}((q))
\]

并且这个迹映射对 torus 的不同标记是协变的（即对 \(\text{SL}(2,\mathbb{Z})\) 等变）。

**关键让步**：不声称「迹的模范变性自动从同调论得出」。而是说：**建立一个因子化迹的定义，使得模范变性等价于迹函子的某种自然变换性质。** 这会将模范变性从「需要手工验证的计算结果」降格为「某个函子的交换图」——这已经是重大进步。

### 6.3 全 CFT 的层论化 🔶

**FRS 定理** ✅：全 RCFT ↔ MTC 中的 Frobenius 代数。

**层论翻译目标**：

> 全 CFT = Ran 空间上的一个因子化层 \(\mathcal{F}\)，使得两个手征分量的限制 \(\mathcal{F}|_{\text{hol}}\) 和 \(\mathcal{F}|_{\text{anti-hol}}\) 满足一个 Frobenius 条件，该条件编码了左右交换的精确方式。

**具体研究计划**：
1. 重新表述 FRS 定理在 chiral 语言中（对已知 RCFT）
2. 推广到允许非有理情形：连续谱 CFT（\(c=1\) 的紧致化族，Haagerup 融合范畴）
3. 建立「Frobenius 条件」在 Ran 空间上的层论版本——可能涉及某种双代数结构的扭转

### 6.4 幺正性的 Hodge 理论化（修正版） ❓/💀

初稿将幺正性 ≈ Hodge 结构视为一个建议。但需要面对一个基本张力：

**Hodge 结构是基于实代数几何的（需要共轭操作），而 BD/GR 框架是完全复的。**

连接两者的可能桥梁：

1. **实因子化代数**（Costello–Gwilliam 进路）：定义在带边界的实流形上的因子化代数，配备一个反射正性条件。这个进路在量子力学（1D）中是成功的——反射正性 ⇔ Hilbert 空间正定性。困难：如何将这个推广到 2D 并保持与 BD 框架的联系。

2. **Harish-Chandra 对**：类似于实 Lie 群 ↔ 复 Lie 代数 + 实形式的关系。幺正 CFT = 复手征代数 + 一个「实结构」（共轭对合），使得反射正性等价于某种正定条件。

3. **最简单的第一步** 🔶：先在具体例子中建立桥梁。取 \(c=1\) 自由玻色子——它是幺正的。显式地写出它在 BD 框架中的手征代数，然后在因子化同调上定义一个正定 Hermitian 形式，验证它满足反射正性。从这个例子中提取通用模式。

### 6.5 Grothendieck–Teichmüller 与对数 CFT 的模 ❓

**已知的精确连接**：
- Drinfeld 关联子（KZ 方程的单值化）是 \(\widehat{\text{GT}}\) 的元素
- KZ 方程的手征部分由 Virasoro（或仿射 Lie 代数）的退化场方程控制
- Drinfeld 关联子的辫子关系 ⇔ VOA 模的融合张量积的结合约束

**精确猜想**：

> 设 \(\mathcal{C}_V\) 是 handside CFT \(V\)（不一定是有理的）的模范畴。则 \(\mathcal{C}_V\) 的辫子张量范畴结构等价类由 \(\widehat{\text{GT}}\) 在关联子组成的空间上的作用中**分类**。

**第一个可计算的测试** 🔶：

取 triplet \(W_p\) 代数（最简单的对数 VOA），计算其模范畴的 Drinfeld 关联子。说明：
- 对于有理 CFT（如 Virasoro 极小模型），Drinfeld 关联子是「有理的」（由单位根给出）
- 对于 \(W_p\)，Drinfeld 关联子的分量包含**对数项**——这正是 Drinfeld 关联子的超越性在模范畴中的表现
- 对应对数 CFT 的「额外难度」 = \(\widehat{\text{GT}}\) 的非 Abel 性质

**如果成功**：对数 CFT 的复杂性将被还原为 \(\widehat{\text{GT}}\) 的群论性质——一个已有丰富理论和计算工具的领域。

### 6.6 共形 bootstrap 的几何起源 ❓（新增）

初稿完全忽略了共形 bootstrap，这是一个重要的遗漏。

**Bootstrap 的核心方程**：对于 CFT 的标量场四点函数，crossing 对称性给出：

\[
\sum_{\mathcal{O}} C_{12\mathcal{O}} C_{34\mathcal{O}} G_{\mathcal{O}}(z, \bar{z}) = \sum_{\mathcal{O}} C_{14\mathcal{O}} C_{23\mathcal{O}} G_{\mathcal{O}}(1-z, 1-\bar{z})
\]

**猜想（共形 bootstrap 的几何对应）**：

> Crossing 方程是**因子化同调在亏格 0、四点标记的 Riemann 面上的两种不同分解之间的同构**。

具体地说：四点函数可以通过两种不同的融合通道（s-通道和 t-通道）计算。在因子化同调语言中，这对应着将四点曲线 \(\mathbb{CP}^1 \setminus \{0, z, 1, \infty\}\) 分解为两个三点曲线（pants decomposition）的两种不同方式：

\[
\int_{\mathbb{CP}^1 \setminus \{0, z, 1, \infty\}} V \simeq \int_{\text{s-通道分解}} V \simeq \int_{\text{t-通道分解}} V
\]

Crossing 方程 => 这两个分解给出的共形块空间之间的同构。但不仅如此——这应该对**所有**共形块同时成立（多个 \(\mathcal{O}\) 求和）。

**如果这个表述正确**：
- Crossing 对称性 = 因子化同调对不同 pants 分解的**协变性**（类似于拓扑量子场论中的 Frobenius 代数公理的 crossing 对称性）
- 共形 bootstrap 的有效性 = crossing 方程的解空间在适当条件下是**有限维的**（等价于共形块空间的有限维性）
- 数值 bootstrap 的 rigourus 基础 = crossing 方程 + 幺正性条件（反射正性）确定解空间的凸性

---

## 7. 结论

### 7.1 我们知道了什么（按确信度分级）

**定理级别** ✅：
- VOA ⟷ 手征代数（BD 等价）
- 有理 CFT = VOA + MTC + FRS Frobenius 代数（Huang 2005, FRS 2002–2007）
- WZW 共形块 ⟷ 几何 Langlands 的 Hecke 特征 D-模（Feigin–Frenkel, BD）
- Geometric Satake（Mirković–Vilonen, Ginzburg）
- Zhu 定理（模范变性）

**部分已知但未完成** 🔶：
- 非半单 CFT/TFT 对应（Hofer–Runkel 进展中）
- 因子化同调在 CFT 中的应用（定义存在，计算几乎不存在）
- 导出代数几何的手征代数（GR 框架提供了语言，但未应用于具体 CFT 例子）
- 幺正 CFT 的完整分类（有理 CFT 完成，非有理 CFT 未完成）

**可以精确表述的猜想** ❓：
- 导出共形块的存在性（对对数 CFT）
- 因子化迹的模协变性（从因子化同调框架）
- 全 CFT 的 Frobenius 层论
- GT 群作用在对数 CFT 模空间上

**需要新数学的猜想** 💀：
- \(\mathbb{F}_1\) 上的 Hodge 实现（CFT = \(\mathbb{F}_1\)-motif 的 Hodge 实现）
- 幺正性的代数几何化（极化手征代数）
- CFT 的「Weil 猜想」（模范变性 = Grothendieck–Lefschetz 迹公式）

### 7.2 Grothendieck 如果还活着会怎么做？

他不会去分类 CFT 的具体例子。他会从**因子化位点的拓扑斯理论**开始：

1. 定义母范畴 \(\text{Ch}(\text{Ran}_X)\) —— 所有手征代数的容纳之所
2. 证明 \(\text{Ch}(\text{Ran}_X)\) 是某个 Tannakian 范畴（或导出 Tannakian 范畴）
3. 识别其 Tannakian 基本群为 **Grothendieck–Teichmüller 群** \(\widehat{\text{GT}}\)（或更精确地，motivic Galois 群 of \(\mathcal{M}_{g,n}\)）
4. 从这个等价中自动导出模范变性（作为函子性）、Verlinde 公式（作为迹公式）、ADE 分类（作为 Tannakian 重构的有限子群分类）

这本书可能叫 *SGA 8: Champs de chiralité*。

### 7.3 现在可以做什么

这个纲领太大，不可能由一个人完成——就像 EGA/SGA 也不可能由 Grothendieck 一个人完成（Bourbaki 的集体力量、Serre 的贡献、Deligne 的后续工作）。

但以下事情可以在当前完成：

1. **计算一个具体的导出共形块**：\(W_p\) 模型在亏格 0 的导出共形块，验证它与已知的共形块结果一致，然后推广到亏格 1。这将是「导出共形块」的第一个非平凡例子。

2. **将 FRS 定理翻译为层论语言**：写下一个精确的层论命题，使得 FRS 构造是其特殊情况。如果可能，给出一个比 FRS 原始证明更概念化的证明（使用因子化层的特殊化函子而非具体的代数运算）。

3. **建立 bootstrap = 因子化同调分解的精确对应**：在最简单的情形（Virasoro 极小模型四点函数），显式地写下因子化同调的两种分解，证明 crossing 对称性恰好等价于两种分解之间的典范同构。

4. **验证 GT-对数 CFT 猜想的最简单情况**：\(W_2\) 模型（triplet 代数在 \(p=2\)），计算其模范畴的 Drinfeld 关联子分量，验证它包含对数项。

每一项都是具体可做的，每一项都在推进纲领，每一项都可能产生可发表的数学论文。

---

## 参考文献

- A. Beilinson, V. Drinfeld, *Chiral Algebras*, AMS Colloquium Publications, 2004.
- Y.-Z. Huang, *Vertex operator algebras, the Verlinde conjecture, and modular tensor categories*, PNAS 102 (2005).
- J. Fuchs, I. Runkel, C. Schweigert, *TFT construction of RCFT correlators I–V*, Nucl. Phys. B (2002–2007).
- A. Ayala, J. Francis, H. Tanaka, *Factorization homology of stratified spaces*, Selecta Math. (2017).
- A. Hofer, I. Runkel, *Non-semisimple CFT/TFT correspondence I*, arXiv:2511.21231 (2025).
- E. Frenkel, D. Ben-Zvi, *Vertex Algebras and Algebraic Curves*, AMS 2001.
- D. Gaitsgory, N. Rozenblyum, *A Study in Derived Algebraic Geometry*, AMS 2017.
- R. Borcherds, *Monstrous moonshine and monstrous Lie superalgebras*, Invent. Math. 109 (1992).
- I. Frenkel, J. Lepowsky, A. Meurman, *Vertex Operator Algebras and the Monster*, Academic Press, 1988.
- Y. Zhu, *Modular invariance of characters of vertex operator algebras*, JAMS 9 (1996).
- S. Rychkov, *Conformal bootstrap: from Polyakov to our times*, arXiv:2509.02779 (2025).
- C. Guillarmou, A. Kupiainen, R. Rhodes, V. Vargas, *Conformal bootstrap in Liouville Theory*, Acta Mathematica 233 (2024).
- A. Belavin, A. Polyakov, A. Zamolodchikov, *Infinite conformal symmetry in two-dimensional quantum field theory*, Nucl. Phys. B241 (1984).
- K. Costello, O. Gwilliam, *Factorization Algebras in Quantum Field Theory*, Cambridge 2017/2021.
- B. Feigin, E. Frenkel, *Affine Kac–Moody algebras at the critical level and Gelfand–Dikii algebras*, Int. J. Mod. Phys. A7 (1992).
- I. Mirković, K. Vilonen, *Geometric Langlands duality and representations of algebraic groups over commutative rings*, Ann. Math. 166 (2007).
- G. Segal, *The definition of conformal field theory*, in *Topology, Geometry and Quantum Field Theory*, LMS 2004.
- J. Lurie, *On the classification of topological field theories*, in *Current Developments in Mathematics 2008*.

---

*初稿写于 2026 年 6 月 26 日。修订版同日完成，新增：数学成熟度标注、导出代数几何（GR）的集成、bootstrap 的几何起源、\(\mathbb{F}_1\) 猜想的三层精确化、GT-对数 CFT 的具体计算方案、以及第 6 节的扩展研究路径。*
