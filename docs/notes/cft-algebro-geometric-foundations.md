# 走向共形场论的代数几何基础

## ——一份关于 Grothendieck 纲领的私人笔记

---

**日期**：2026-06-26

**摘要**：本文勾勒一个用纯代数几何方法建立二维共形场论数学基础的纲领。核心论点是：(1) CFT 与数论的关系远比「使用模形式作为工具」深刻——两者通过几何 Langlands 纲领共享结构 DNA；(2) Beilinson–Drinfeld 手征代数 + 因子化同调已经提供了「EGA for CFT」的语言，但目前缺少非手征情形、特征标公式、对数情形和幺正性条件的统一处理；(3) 一个真正深刻的基础可能需要从因子化位点的拓扑斯理论出发。

---

## 1. 引言：基础在哪里？

二维共形场论的数学基础在 1984 年（BPZ 论文）到 2005 年（Huang 的 Verlinde 猜想证明）之间，对**有理 CFT**（rational CFT）建立了一条逻辑自洽的完整链条：

\[
\text{顶点算子代数（VOA）} \longrightarrow \text{模张量范畴（MTC）} \longrightarrow
\begin{cases}
\text{手征关联子（Huang–Lepowsky 张量范畴）} \\
\text{全 CFT 关联子（Fuchs–Runkel–Schweigert Frobenius 代数）}
\end{cases}
\]

这条链上的每一步都是定理而非猜想。在这个意义上，有理 CFT 拥有与「量子力学由 Hilbert 空间 + 自伴算符代数描述」同等严格的数学基础。

然而，这是一个局部胜利。

有理 CFT 是全体 2D CFT 中一个**测度为零的子集**。绝大多数物理上有趣的 CFT——包括 \(c=1\) 紧致化自由玻色子（连续族）、Liouville 理论（连续谱）、渗透模型（\(c=0\)，对数 CFT）、自规避行走（\(c=-2\)，非幺正）——都落在有理 CFT 的范围之外。

更根本地说，当前所有进路——VOA 及其推广、模张量范畴、FRS 构造——都依赖于一个可能在一般 CFT 中不成立的假设：**手征分裂**（chiral factorization），即全理论可以分解为左右手征部分的某种组合。对于对数 CFT，全理论的模空间甚至不等同于左右手征模空间的张量积。

此外，当前有四套互不兼容的数学语言在平行发展：

1. **代数路径**（VOA + 张量范畴）：Huang–Lepowsky–Zhang，半单 → 非半单推广。
2. **概率路径**（GFF + GMC + SLE）：David–Kupiainen–Rhodes–Vargas，仅对 Liouville 理论完全严格化。
3. **算子代数路径**（共形网）：Longo–Kawahigashi，仅适用于幺正理论。
4. **因子化代数路径**（Costello–Gwilliam, Beilinson–Drinfeld）：最一般的概念框架，但缺乏计算工具。

状态十分类似于 1950 年代中期的代数几何：

| Grothendieck 之前的代数几何 | 当前的 CFT 数学基础 |
|---|---|
| 意大利学派：用具体方程和几何直觉研究代数曲面 | BPZ + 物理传统：用作用量、路径积分、物理直觉研究 CFT |
| Zariski 拓扑：用代数集定义拓扑，笨拙且不函子化 | VOA + OPE：用局部场展开定义结构，严格但不函子化 |
| Serre FAC (1955)：层论出现，但基础仍建立在复点集上 | Huang 2005：VOA 模的张量范畴，但基础仍建立在形式幂级数上 |
| **Grothendieck EGA (1960–69)**：概形语言，一切层论化、函子化 | **尚未出现** |

如果我们接受这个类比，那么 CFT 的「EGA 时刻」可能需要一个能够同时容纳有理 CFT、对数 CFT 和连续谱理论的统一代数几何框架。

本文的目的是勾勒这样一个框架的初步设想。

---

## 2. CFT 与数论

### 2.1 工具层面 vs. 结构层面

CFT 与数论最常见的关系是工具层面的：模形式出现在 torus 配分函数中，VOA 特征标是模形式，Verlinde 公式涉及代数数。但这只是冰山一角。

真正的连接在结构层面。

### 2.2 月光：第一条线索

1978 年，John McKay 注意到：

\[
196884 = 1 + 196883
\]

等式左边是椭圆模函数 \(j(\tau) = q^{-1} + 744 + 196884q + \cdots\) 的 Fourier 系数。右边：1 是平凡表示的维数，196883 是 Monster 单群（最大的散在有限单群）的最小非平凡不可约表示的维数。

这不是巧合。Conway–Norton（1979）提出了**月光猜想**（Monstrous Moonshine）：

> 存在一个分次无限维 Monster 模，使得每个群元素在该模上的分次迹恰好是某个 genus 0 子群的主模（Hauptmodul）。

Frenkel–Lepowsky–Meurman（1988）构造了**月光模 \(V^\natural\)**——一个顶点算子代数，满射自同构群恰好是 Monster 单群 \(\mathbb{M}\)。Borcherds（1992）证明了 McKay–Thompson 级数恰好是所预测的主模，因此获得 1998 年菲尔兹奖。

月光建立了第一个深层的 CFT-数论连接：**有限群论 ↔ 自守形式 ↔ 顶点代数**。

但这不是终点，只是序章。

### 2.3 Zhu 定理与模不变性的算术化

Zhu（1996）证明的定理是 CFT-数论连接的**算术化步骤**：

> **Zhu 定理**：设 \(V\) 为有理、\(C_2\)-余有限的 VOA。则其不可约模的特征标 \(\chi_M(\tau) = \operatorname{tr}_M q^{L_0 - c/24}\) 组成的向量值函数在模群 \(\text{SL}(2,\mathbb{Z})\) 的作用下按某个有限维表示变换：
> \[
> \chi_M(-1/\tau) = \sum_N S_{MN} \chi_N(\tau), \qquad \chi_M(\tau+1) = \sum_N T_{MN} \chi_N(\tau)
> \]

**数论语言翻译**：VOA 的特征标是某个同余子群上的**向量值模形式**。

这使得数个经典的数论性质自动转移到 CFT 中：

- 模形式的 Fourier 系数是整数 → VOA 的分次维数是整数
- \(S\)-矩阵的矩阵元是代数数 → 量子维数是 \(\mathbb{Q}(e^{2\pi i / \kappa})\) 中的代数整数
- Verlinde 公式 \(N_{ab}^c = \sum_d \frac{S_{ad} S_{bd} S_{cd}}{S_{0d}}\) 保证融合系数是非负整数

这与数论中的经典模式完全平行：**模形式 → Galois 表示 → L-函数 → 特殊值 → 代数性定理**。

### 2.4 几何 Langlands：最深层的连接

这是 CFT 与数论关系的**结构核心**。

**经典 Langlands 纲领**（1967–）：数域的 Galois 表示 ↔ 自守表示。核心猜想：对 \(\text{Gal}(\overline{\mathbb{Q}}/\mathbb{Q})\) 的每个 \(n\) 维表示，存在 \(\text{GL}_n(\mathbb{A}_{\mathbb{Q}})\) 上的自守表示与之对应，且 L-函数相等。

**函数域 Langlands**（Drinfeld 1974, Lafforgue 2002）：将 \(\mathbb{Q}\) 替换为有限域上的函数域 \(\mathbb{F}_q(X)\)。此时 \(\text{Gal}\) 侧变为曲线的 étale 基本群，自守侧变为 \(\text{Bun}_G(X)\) 上的函数。

**几何 Langlands 纲领**（Beilinson–Drinfeld 1990s–）：将 \(\mathbb{F}_q\) 替换为 \(\mathbb{C}\)，将 \(\ell\)-adic 层替换为 D-模。核心陈述：

\[
D\text{-模}(\text{Bun}_G(X)) \longleftrightarrow \text{QCoh}(\text{Loc}_{G^L}(X))
\]

左侧是 \(G\)-主丛模叠上的 D-模（中心荷为临界的 Hecke 特征 D-模），右侧是对偶群 \(G^L\) 的局部系统模叠上的 quasi-coherent 层。

**CFT 的角色**：

> **WZW 模型在临界 level \(k = -h^\vee\) 的共形块恰好是几何 Langlands 的 Hecke 特征层。**

具体地说：

\[
\text{WZW 共形块} \xrightarrow{\text{精确对应}} \text{Hecke 特征 D-模}
\]

在这个对应中：

- **共形块空间** → 仿射 Grassmannian 上的 critical level 模的全局截面
- **BPZ 方程**（退化场的微分方程） → Hecke 特征条件
- **OPE 结合性** → **geometric Satake 等价**（Mirković–Vilonen, Ginzburg, Beilinson–Drinfeld）：\(\text{Rep}(G^L) \simeq \text{Perv}_{\text{GO}}(\text{Gr}_G)\)
- **融合规则** → geometric Satake 中的张量积
- **模不变性** → 共形块丛在 \(\overline{M}_g\) 上的平坦联络（Hitchin 联络）

追踪这个对应，我们得到一个惊人的结论：

> **CFT 是几何 Langlands 对偶的「引擎」——实现对偶的具体代数/几何机制。**

这意味着 CFT 与数论的关系比「使用模形式作为工具」深刻了整整一个范畴层级。两者是**同一结构在复曲线和数域两个不同基底上的表观**。

---

## 3. Grothendieck 进路：Segal 公理、手征代数、因子化同调

### 3.1 Segal 的函子 CFT

Graeme Segal 在 1980–1990 年代提出了一个激进的想法：**CFT 是一个函子**。

设 \(\mathcal{C}\) 为下述范畴：

- **对象**：\(S^1\) 的有限多个拷贝（参数化的边界圈）
- **态射**：带参数化边界的 Riemann 面（配边）
- **合成**：边界的缝合
- **对称幺半结构**：不交并

则一个 CFT 是函子：

\[
Z: \mathcal{C} \longrightarrow \text{Hilb}
\]

满足：

1. \(Z(S^1 \sqcup S^1) = Z(S^1) \otimes Z(S^1)\)（幺半性）
2. 共形映射下协变
3. 缝合（态射合成）对应算符的迹

**这个框架的力量**：它第一次将 CFT 定义为**范畴之间的函子**，而非在特定时空上满足一组偏微分方程的解。这是一个真正的 Grothendieck 式定义。

**这个框架的问题**：

- Segal 公理在亏格 0 和 1 上等价于标准 CFT 定义。但对于**高亏格**，他需要手工加上模不变性——这不是从公理导出的，是附加上去的。
- 对于非有理 CFT（连续表示谱），Segal 的公理中需要的「trace class」条件会崩溃——Hilbert 空间的张量积上不一定存在迹。
- 对于对数 CFT，全理论和手征部分之间的 Segal 缝合结构在非半单情况下不明确。

所以 Segal 的框架是正确的哲学方向，但它的数学实现还没有达到 Grothendieck × Serre 的完备性。

### 3.2 Beilinson–Drinfeld 手征代数：最接近 EGA 的东西

**Beilinson–Drinfeld**（*Chiral Algebras*, AMS 2004）在 1990 年代发展的手征代数理论，是目前最接近 Grothendieck 式 CFT 基础的进路。

#### 3.2.1 Ran 空间

BD 框架的基础对象不是时空区域，而是 **Ran 空间**：

\[
\operatorname{Ran}(X) = \{ \text{\(X\) 的所有有限非空子集} \}
\]

其上赋予的拓扑（或更准确地，位点结构）使得：
- 开集是「在有限多个点上同时取值的截面」
- 层的定义自然携带「在点碰撞时的极限行为」

这完全平行于 Grothendieck 的洞见：代数几何的「局部模型」不是开集，而是交换环的谱。CFT 的「局部模型」也不是时空区域，而是曲线上的**形式邻域**，其「代数」是顶点代数。

#### 3.2.2 手征代数 = Ran 空间上的因子化层

定义（精简版）：

> **手征代数** \(\mathcal{A}\) 是 Ran 空间上的一个 D-模层（或拟凝聚层），配备一个因子化同构：
> \[
> \mathcal{A}(I \sqcup J) \xrightarrow{\sim} \mathcal{A}(I) \boxtimes \mathcal{A}(J)
> \]
> 其中 \(I, J\) 是 \(X\) 的互不相交的有限子集。

这个「因子化结构」恰好编码了 CFT 的 OPE：在点重合时，两个局部场的乘积展开为单一场的无穷级数。层的语言将这种**微扰展开自动处理为形式邻域上的极限过程**。

#### 3.2.3 核心定理

> **BD 等价定理**：在光滑复代数曲线 \(X\) 上，存在一个范畴等价：
> \[
> \left\{ \text{\(X\) 上的手征代数} \right\} \longleftrightarrow
> \left\{ \text{顶点代数} + \text{\(X\) 上的形式邻域数据} \right\}
> \]

换句话说：**顶点代数 = 手征代数的局部截面**。就像交换环 = 仿射概形的全局截面，李代数 = 形式群的无穷小结构。

这使得 CFT 从「平面 \(\mathbb{C}\) 上的代数结构」**几何化**为「任意复曲线 \(X\) 上的全局对象」。

#### 3.2.4 Beilinson–Drinfeld 框架中已经可以做的事

| 标准 CFT 概念 | 手征代数翻译 |
|---|---|
| 顶点代数 \(V\) | Ran 空间上的手征代数层 |
| 真空态 | 层的单位截面 |
| 保形向量 | 从 Virasoro 代数的普遍包络代数的态射 |
| 共形块 | 手征代数的 de Rham 上同调（在 Ran 空间上） |
| 融合规则（亏格 0） | Ran 空间上的特殊化函子的 monodromy |
| 模不变性（亏格 1） | 模叠上的手征代数的下降条件 |
| 高亏格共形块 | 曲线上手征代数的因子化同调 |
| Hecke 特征层 | 临界 level 手征代数的模 |

**目前缺什么**：

1. **非手征理论**：BD 框架主要处理手征（holomorphic）CFT。全理论（左右交换手征代数的张量积）需要某种「\(X\) 的实形式上的因子化结构」——这还没有被完整函子化。

2. **幺正性条件**：如何在代数几何框架中内建幺正性？在 BD 框架中，幺正性目前是手工强加的条件——就像在交换代数中手工要求一个交换环「有正性」。共形网（von Neumann 代数网）的进路中，幺正性内置于 III₁ 型因子的模理论，但代数几何缺少对应的概念。可能的进路：通过某种形式的 **Hodge 结构** 或 **极化**——回想复几何中，正性可以通过 Kähler 度量和 Hodge 结构来形式化。

3. **对数/非半单理论**：\(C_2\)-余有限条件在 BD 框架中对应什么？非 \(C_2\)-余有限手征代数（如对数 CFT 的 VOA）的 Ran 空间行为完全不清楚。

### 3.3 因子化同调：从代数到拓扑不变量的函子式过渡

**因子化同调**（Ayala–Francis–Tanaka, 2017–2025）是过去十年最激动人心的新工具。

**核心构造**：给定一个 \(n\)-碟片代数（\(E_n\)-algebra）\(\mathcal{A}\) 和一个带框架的 \(n\)-流形 \(M\)，因子化同调

\[
\int_M \mathcal{A}
\]

是一个链复形（或导出范畴中的对象），其同调是实现 \(\mathcal{A}\) 在 \(M\) 上的「拓扑编织」的不变量。

**对于 CFT**：一个顶点代数 \(V\) 是一个 \(\mathbb{R}^2\) 上的 \(E_2\)-代数（或更准确地说，一个手征代数）。对于带复结构的 Riemann 面 \(\Sigma\)，

\[
\int_\Sigma V
\]

自动复现**共形块空间**。

这之所以重要，是因为：

1. **不需要坐标**：传统 CFT 中，共形块的构造依赖于局部坐标（Virasoro 生成元用复数坐标 \(z, \bar{z}\) 表示），高亏格时需要拼贴坐标卡。因子化同调是纯函子式的：它只依赖于 \(V\) 的代数结构和 \(\Sigma\) 的拓扑/几何，不需要做任何坐标选择。

2. **自然推广到对数 CFT**：因子化同调在非半单情况下仍然是定义良好的导出函子。这使得「对数 CFT 的共形块」可以被自然地定义为导出对象——当前用传统方法构造这些东西极其困难。

3. **特征标公式**：经典的 VOA 特征标 \(\chi_M(\tau) = \operatorname{tr}_M q^{L_0 - c/24}\) 在因子化同调语言中是

\[
\operatorname{tr}\left( \int_{T^2} V \right)
\]

即 torus 上因子化同调的某种分次迹。这暗示模不变性（在 \(S: \tau \mapsto -1/\tau\) 下的协变性）应该能从因子化同调的函子性中**自动导出**——当前模不变性必须作为「手工条件」强加于特征标上，但在因子化同调框架中，torus 的不同标记（\(a\)-圈与 \(b\)-圈的交换）对应着曲面分解的不同方式，而因子化同调对此自动协变。

这是可能的**卷 III**的内容——将模不变性从「需要手工验证的条件」升格为「因子化同调函子性的定理」。

---

## 4. 设想中的「EGA for CFT」

基于以上三个支柱——手征代数、因子化同调、几何 Langlands——可以勾勒一个完整的纲领。以下是一个概念性的目录。

### 卷 0：CFT 的相对视角

**核心原则**：不研究孤立的 CFT，而研究 CFT 在基曲线**族**上的行为。

在 Grothendieck 的代数几何中，我们不研究「一个代数簇 \(X\)」，而是研究态射 \(f: X \to S\)——\(X\) 是 \(S\) 上的相对概形。这使得我们可以利用基变换、平滑态射的性质、上同调的基变换定理等。

类似地，CFT 的相对视角：

> 给定一族光滑曲线 \(\pi: \mathcal{X} \to S\)，一个**相对 CFT** 是 Ran\((\mathcal{X}/S)\) 上的一个手征代数（或手征代数的层），满足基 \(S\) 上的平坦性条件。

这使得我们可以做以下在孤立的「一个 CFT」上无法做到的事情：

- **基变换**：CFT 在退化曲线族上的极限行为
- **下降**：模叠上的 CFT（模不变性的自然出现）
- **模空间上的 D-模结构**：Hitchin 联络作为 Gauss–Manin 联络

### 卷 I：CFT 的「拓扑」——因子化位点

**内容**：
- Ran 位点与 Ran 空间的拓扑斯理论
- 因子化层：定义、基本性质、因子化代数的范畴
- **核心定理**：顶点代数 \(\leftrightarrow\) Ran 空间上具有曲率自由的因子化 D-模层（沿袭 Beilinson–Drinfeld 的方法，但完全以层论语言重写）
- 因子化位点上的拟凝聚层、D-模、perverse 层
- 因子化层沿闭嵌入的拉回和特殊化

### 卷 II：CFT 的「同调」——因子化同调

**内容**：
- 因子化同调的严格定义：\(\int_\Sigma: \text{Alg}^{\text{Fact}}(\text{Ran}_X) \to \text{Ch}\)
- **核心定理**：对于 \(C_2\)-余有限手征代数，\(\int_\Sigma V\) 是有限维链复形，其同调 \(\simeq\) 传统共形块空间
- 因子化 Künneth 公式：缝合 ⇔ 因子化同调的张量积
- 非半单情形：导出共形块与余同调集中的重数
- **关键应用**：映射类群在 \(\int_\Sigma V\) 上的作用（因子化同调的拓扑不变性 ⇒ 映射类群表示）

### 卷 III：CFT 的「上同调」——特征标与自守性

**内容**：
- 因子化迹 \(\operatorname{Tr}^{\text{fact}}: K_0(\text{FactAlg}) \to \text{ModForms}\)
- **核心猜想**：对 torus 上的因子化同调，迹自动满足模协变性——不需要手工强加
- 因子化迹 → 模叠上的局部系统 → 特征标 → 向量值模形式
- Verlinde 公式作为因子化迹的分解定理
- 特征标的 Galois 性质：\(S\)-矩阵的矩阵元是代数整数

**理念**：这里的「上同调」应该被理解为某种层上同调的迹公式。在 étale 上同调中，Grothendieck–Lefschetz 迹公式联系了点计数和 Galois 表示的迹。类似地，CFT 的特征标应该是某种「因子化上同调」的迹，而模不变性——\(\tau \mapsto -1/\tau\) 的协变性——应该是 torus 的**不同几何标记**之间的同构在因子化同调上的表现。

### 卷 IV：CFT 的「Galois 理论」

**内容**：

CFT 的分类应该用表示论的范畴层级来描述：

| CFT 类型 | 表示范畴 | 类比于数域扩张 |
|---|---|---|
| 有理 CFT | 半单模张量范畴 | 有限 Galois 扩张 |
| 对数 CFT | 有限非半单辫子张量范畴 | 局域域的有限分歧扩张 |
| 非有理非对数 CFT | 无穷多简单对象的辫子张量范畴 | 无穷 Galois 扩张 |
| 一般 CFT | ? | 绝对 Galois 群 \(\text{Gal}(\overline{\mathbb{Q}}/\mathbb{Q})\) 的表示 |

**核心猜想**（手征代数的 Galois 对应）：

> 设 \(X\) 为 \(\mathbb{C}\) 上亏格 \(g\) 的光滑射影曲线。则存在一个范畴等价：
> \[
> \left\{ \text{\(X\) 上的 \(C_2\)-余有限手征代数} \right\}
> \longleftrightarrow
> \left\{ \pi_1^{\text{ét}}(\mathcal{M}_{g,n}) \text{ 的有限维射影表示} \right\}
> \]

这张图的左侧是 CFT 数据，右侧是纯数论数据。Hitchin 联络和 TUY 共形块定理已经证明了从左侧到右侧的箭头。猜想要求这个箭头是**范畴等价**。

如果这个猜想成立：

- CFT 的分类 = Galois 表示（映射类群表示）的分类。
- Verlinde 公式是某种 Artin L-函数的特殊值。
- 模不变性是 Galois 表示的 Frobenius 迹公式（通过 \(\text{SL}(2,\mathbb{Z})\) 在 torus 上的模作用）。
- 对数 CFT → 非半单 Galois 表示（\(\ell\)-adic 表示的模 \(p\) 约化？局部域的 p-进表示？）
- 「绝对 Galois 群」在此是**映射类群** \(\Gamma_{g,n}\) 或更神秘地——**Grothendieck–Teichmüller 群** \(\widehat{\text{GT}}\)。

---

## 5. \(\mathbb{F}_1\) 视角：最深层的猜想

上述猜想在已发表的数学文献中部分是已知的（手征代数 ↔ 顶点代数），部分是半已知的（Hitchin 联络 → 模叠上的局部系统），部分是猜想性的（范畴等价，非半单版本的完整表述）。

但更深层的问题是：**为什么 CFT 的结构和数论的结构如此相似？**

一个可能的答案是：**两者都是某种「\(\mathbb{F}_1\) 上的代数几何」的不同实现**。

「一元域」\(\mathbb{F}_1\) 上的几何（Soulé 2004, Connes–Consani 2010, Scholze 的钻石等）是一个纲领，其核心洞见是：当我们将经典的 \(\mathbb{Z}\) 上代数几何「下降到 \(\mathbb{F}_1\)」时，许多不同的结构（组合数学、热带几何、谱的三明治）统一为同一个对象。

**\(\mathbb{F}_1\)-猜想**：

> CFT 是 \(\mathbb{F}_1\) 上的某种上同调理论在 \(\mathbb{C}\) 上的 **Hodge 实现**。

这意味着：

- **模形式**（CFT 特征标）= 某种 \(\mathbb{F}_1\)-motif 的 Hodge 实现
- **VOA 的分次维数**（模形式的 Fourier 系数）= \(\mathbb{F}_1\) 上的点计数（对于「\(\mathbb{F}_{1^n}\)」的 \(n \to \infty\) 极限）
- **Verlinde 公式** = \(\mathbb{F}_1\) 上的 Grothendieck–Lefschetz 迹公式
- **融合规则** = \(\mathbb{F}_1\) 上的交理论
- **几何 Langlands for CFT** = \(\mathbb{F}_1\) 上函数域 Langlands 的 Hodge 对应

这听起来荒谬，但有具体的线索：

1. Huang 的 modular tensor category 构造在 D-模语言中对应于 factorizable sheaf。而 factorizable sheaf 是 \(\mathbb{C}\)-线性结构。对应的 \(\mathbb{F}_1\)-结构可能是 combinatorial factorizable sheaf（其 heart 是某种 finite pointed set 范畴上的层）。

2. VOA 的分次维数是**正整数**——这些整数的起源在 CFT 中始终没有令人满意的解释（它们「恰好」是模形式的 Fourier 系数）。在计数几何中，正整数来自 \(\mathbb{F}_q\) 上的点计数。\(\mathbb{F}_1\)-视角为这些整数的出现提供了结构性理由：它们是 \(\mathbb{F}_1\) 上「motif 的秩」。

3. 最近 Ang–Sun–Wu（2024）对 SLE loop 测度的精确公式涉及大量的**整数**（某种组合量的精确计数），这暗示 SLE/LCFT 的概率结构中隐藏着一个组合/计数几何核心——\(\mathbb{F}_1\)-几何的典型特征。

---

## 6. 当前的技术前沿与具体的下一步

与其停留在纲领性的猜想上，以下是几条可以在目前数学水平上推进的具体研究方向。

### 6.1 导出共形块与非半单情形

Huang–Lepowsky 的顶点张量范畴构造在非半单情形（对数 CFT）遇到的根本技术问题是：VOA 的模在非半单时未必有良好定义的**迹**。传统共形块通过取特定空间的对偶定义——在非半单时，对偶和迹的定义需要导出范畴的框架。

**具体问题**：定义 triplet \(W_p\) 代数在任意亏格 \(g \ge 1\) 的 Riemann 面上的**导出共形块**，计算其维数（或 Euler 示性数），并验证它们在形变下的不变性。

当前工具：因子化同调（Ayala–Francis）+ 导出代数几何（Toën–Vezzosi）。

### 6.2 Torus 特征标的因子化同调推导

**具体猜想**：设 \(V\) 为 \(C_2\)-余有限手征代数。则存在规范同构：

\[
\operatorname{Tr}^{\text{fact}}\left( \int_{T^2_\tau} V \right) \xrightarrow{\sim} \operatorname{Tr}^{\text{fact}}\left( \int_{T^2_{-1/\tau}} V \right)
\]

使得特征标 \(\chi_M(\tau)\) 自动满足模协变性，而不需要将其作为独立条件强加。

（已知 Zhu 定理从 VOA 的公理中**证明**了模协变性。但 Zhu 的证明使用了形式幂级数展开——本质上是一个计算。因子化同调版本应该将这个计算升级为范畴等价——就像证明 cohomology 的基变换不用具体的 Čech 计算而用导出范畴的函子性。）

### 6.3 Frobenius 代数对象与全 CFT 的层论化

Fuchs–Runkel–Schweigert 定理：全 RCFT ↔ MTC 中的 Frobenius 代数。在手征代数语言中，这应该被翻译为：

> 全 CFT 是 Ran 空间上的一个因子化层，其两个手征分量的限制满足 Frobenius 条件。

具体构造这个层论版本，并用它来**系统分类**有理 CFT（复现已知的 ADE 分类），然后将它推广到允许的非有理情形——连续谱 CFT（Haagerup 融合范畴、\(c=1\) 的紧致化族）。

### 6.4 幺正性的代数几何化

当前框架中的核心缺失：**幺正性条件没有代数几何表述**。

一个可能的进路：幺正性在复几何中通过 **Hodge 结构** 和 **极化** 来表达。一个预极化 CFT 可能是因子化同调上带有一个 Hermitian 形式和一个正性条件的对象——类似于权 0 的 Hodge 结构带有一个极化。

具体地：如果 CFT = 某个 \(\mathbb{F}_1\)-motif 的 Hodge 实现，那么幺正性可能对应于**纯 Hodge 结构**（权过滤的某种正性条件）。对于非幺正 CFT（如 \(c=-2\) 的 symplectic 费米子），对应的 Hodge 结构将不是纯的，而是**混合 Hodge 结构**。

这是一个完全开放的猜想，但如果正确，它将把 CFT 的分类问题转化为 Hodge 理论的分类问题——一个已经有成熟工具的领域。

### 6.5 Grothendieck–Teichmüller 群与对数 CFT 的模

已知：Grothendieck–Teichmüller 群 \(\widehat{\text{GT}}\) 是 \(\text{Gal}(\overline{\mathbb{Q}}/\mathbb{Q})\) 在映射类群的外自同构群中的自然推广。Drinfeld 关联子（Drinfeld associator）——KZ 方程的单值化——是 \(\widehat{\text{GT}}\) 的元素的典型例子。

**猜想**：

> 对数 CFT 的张量范畴等价类在 \(\widehat{\text{GT}}\) 的作用下封闭，且其模空间是 \(\widehat{\text{GT}}\) 的某个齐性空间。

如果这个猜想正确，对数 CFT 的「额外难度」（相对于有理 CFT）将被还原为 \(\widehat{\text{GT}}\) 的非 Abel 性质——有理 CFT 只涉及 \(\widehat{\text{GT}}\) 的 Abel 商（\(\mathbb{Z}^\times\)，通过根子群），而对数 CFT 涉及整个非 Abel 群。

这条线的具体入手点：计算 triplet \(W_p\) 的 Drinfeld 关联子在张量范畴中的作用，并说明它与 VOA 的自同构的对应。

---

## 7. 结论：Grothendieck 如果还活着会怎么做？

最后，回到最初的问题：CFT 的基础是否已经建立？用纯代数几何方法可以做到什么程度？

当前状态：我们有四套部分重叠的数学语言——VOA/张量范畴、因子化代数/手征代数、概率论（GFF/GMC/SLE）、算子代数（共形网）——各自在特定子领域内取得了定理级别的成就，但它们之间的翻译词典严重不完整。

代数几何进路——具体地说，Beilinson–Drinfeld 手征代数 + 因子化同调——是目前最有希望成为统一框架的候选者。它的优势在于：

1. **已覆盖所有手征 CFT**——包括有理、非有理、对数。
2. **提供「相对视角」**——CFT 在曲线族上的行为自然出现。
3. **与数论/Langlands 的联系内建于框架之中**——不需要额外的猜测。
4. **导出范畴方法自然处理非半单情形**——非半单不是「推广」，而是导出框架的自然一部分。

它的缺失是：

1. 非手征（全）理论的因子化代数描述。
2. 幺正性条件的代数几何表述。
3. 从框架中导出可计算的关联函数（而非仅存在性）。

如果 Grothendieck 今天还在世，他大概率不会去研究「CFT 的分类的具体细节」，而是会从**因子化位点的拓扑斯理论**开始，定义一个包含所有手征代数的**母范畴**，证明它等价于 \(\mathbb{F}_1\) 上某个 motivic Galois 群的表示范畴，并从这个等价中导出 Verlinde 公式作为 \(\mathbb{F}_1\)-迹公式，模不变性作为函子性，ADE 分类作为 Tannakian 重构。这本书可能叫《SGA 8: Champs de chiralité》，它的难度和深度将超过已有的任何 CFT 文献，但在它出版之后，人们会发现有理 CFT、对数 CFT 和 Liouville CFT 原来**一直都是同一件事**。

---

## 参考文献

- A. Beilinson, V. Drinfeld, *Chiral Algebras*, AMS Colloquium Publications, 2004.
- Y.-Z. Huang, *Vertex operator algebras, the Verlinde conjecture, and modular tensor categories*, PNAS 102 (2005).
- J. Fuchs, I. Runkel, C. Schweigert, *TFT construction of RCFT correlators I–V*, Nucl. Phys. B (2002–2007).
- A. Ayala, J. Francis, H. Tanaka, *Factorization homology of stratified spaces*, Selecta Math. (2017).
- A. Hofer, I. Runkel, *Non-semisimple CFT/TFT correspondence I*, arXiv:2511.21231 (2025).
- E. Frenkel, D. Ben-Zvi, *Vertex Algebras and Algebraic Curves*, AMS 2001.
- D. Gaiotto, A. Kapustin, N. Seiberg, B. Willett, *Generalized Global Symmetries*, JHEP 02 (2015).
- R. Borcherds, *Monstrous moonshine and monstrous Lie superalgebras*, Invent. Math. 109 (1992).
- I. Frenkel, J. Lepowsky, A. Meurman, *Vertex Operator Algebras and the Monster*, Academic Press, 1988.
- Y. Zhu, *Modular invariance of characters of vertex operator algebras*, JAMS 9 (1996).
- S. Rychkov, *Conformal bootstrap: from Polyakov to our times*, arXiv:2509.02779 (2025).
- C. Guillarmou, A. Kupiainen, R. Rhodes, V. Vargas, *Conformal bootstrap in Liouville Theory*, Acta Mathematica 233 (2024).
- A. Belavin, A. Polyakov, A. Zamolodchikov, *Infinite conformal symmetry in two-dimensional quantum field theory*, Nucl. Phys. B241 (1984).
