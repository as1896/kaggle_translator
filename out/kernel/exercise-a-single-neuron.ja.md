**このノートブックは、[ディープラーニング入門](https://www.kaggle.com/learn/intro-to-deep-learning)コースの演習です。[このリンク](https://www.kaggle.com/ryanholbrook/a-single-neuron)にあるチュートリアルを参照できます。**

---


# はじめに #

チュートリアルでは、ニューラルネットワークの構成要素である*線形ユニット*について学習しました。単一の線形ユニットだけのモデルでは、データセットに線形関数を適合させます（線形回帰と同等です）。この演習では、線形モデルを作成し、Kerasでのモデルの操作方法を練習します。

始める前に、以下のコードセルを実行してすべてを設定します。


```python
# Setup plotting
import matplotlib.pyplot as plt

plt.style.use('seaborn-whitegrid')
# Set Matplotlib defaults
plt.rc('figure', autolayout=True)
plt.rc('axes', labelweight='bold', labelsize='large',
       titleweight='bold', titlesize=18, titlepad=10)

# Setup feedback system
from learntools.core import binder
binder.bind(globals())
from learntools.deep_learning_intro.ex1 import *
```

*赤ワインの品質*データセットは、約1600種類のポルトガル産赤ワインの理化学的測定値で構成されています。また、ブラインドテイスティングによる各ワインの品質評価も含まれています。

まず、次のセルを実行して、このデータセットの先頭数行を表示します。


```python
import pandas as pd

red_wine = pd.read_csv('../input/dl-course-data/red-wine.csv')
red_wine.head()
```

`shape`属性を使用して、データフレーム（またはNumPy配列）の行数と列数を確認できます。


```python
red_wine.shape # (rows, columns)
```

# 1) 入力形状 #

理化学的測定値からワインの知覚される品質をどの程度正確に予測できるでしょうか？

ターゲットは`'quality'`で、残りの列が特徴量です。このタスクでKerasモデルの`input_shape`パラメーターをどのように設定しますか？


```python
# YOUR CODE HERE
input_shape = ____

# Check your answer
q_1.check()
```


```python
# Lines below will give you a hint or solution code
#q_1.hint()
#q_1.solution()
```

# 2) 線形モデルの定義 #

次に、このタスクに適した線形モデルを定義します。モデルの入力と出力の数に注意してください。


```python
from tensorflow import keras
from tensorflow.keras import layers

# YOUR CODE HERE
model = ____

# Check your answer
q_2.check()
```


```python
# Lines below will give you a hint or solution code
#q_2.hint()
#q_2.solution()
```

# 3) 重みの確認 #

内部的に、Kerasはニューラルネットワークの重みを**テンソル**で表現しています。テンソルは基本的にTensorFlowのバージョンのNumPy配列ですが、ディープラーニングにより適したいくつかの違いがあります。最も重要なものの1つは、テンソルが[GPU](https://www.kaggle.com/docs/efficient-gpu-usage)と[TPU](https://www.kaggle.com/docs/tpu))アクセラレーターと互換性があることです。実際、TPUはテンソル計算のために特別に設計されています。

モデルの重みは、テンソルのリストとしてその`weights`属性に保持されます。上記で定義したモデルの重みを取得します。（必要に応じて、`print("Weights\n{}\n\nBias\n{}".format(w, b))`のようなものを使用して重みを表示できます）。


```python
# YOUR CODE HERE
w, b = ____

# Check your answer
q_3.check()
```


```python
# Lines below will give you a hint or solution code
#q_3.hint()
#q_3.solution()
```

（ちなみに、Kerasは重みをテンソルとして表現しますが、データを表すためにもテンソルを使用します。`input_shape`引数を設定すると、トレーニングデータの各例に対して期待する配列の次元をKerasに伝えます。`input_shape=[3]`を設定すると、`[0.2, 0.4, 0.6]`のような長さ3のベクトルを受け入れるネットワークが作成されます。）


# オプション：訓練されていない線形モデルの出力をプロットする
 
レッスン5を通して取り組む問題の種類は*回帰*問題であり、目標は数値ターゲットを予測することです。回帰問題は「曲線適合」問題に似ています。データに最適に適合する曲線を見つけようとしています。線形モデルによって生成される「曲線」を見てみましょう。（それが線であると推測したかもしれません！）

モデルの重みを訓練する前に、ランダムに設定されることを述べました。ランダムな初期化で生成されるさまざまな線を見るために、以下のセルを数回実行してください。（この演習にはコーディングはありません—単なるデモです。）


```python
import tensorflow as tf
import matplotlib.pyplot as plt

model = keras.Sequential([
    layers.Dense(1, input_shape=[1]),
])

x = tf.linspace(-1.0, 1.0, 100)
y = model.predict(x)

plt.figure(dpi=100)
plt.plot(x, y, 'k')
plt.xlim(-1, 1)
plt.ylim(-1, 1)
plt.xlabel("Input: x")
plt.ylabel("Target y")
w, b = model.weights # you could also use model.get_weights() here
plt.title("Weight: {:0.2f}\nBias: {:0.2f}".format(w[0][0], b[0]))
plt.show()
```

# 続行 #

隠れ層を追加し、レッスン2で[**モデルを深くする**](https://www.kaggle.com/ryanholbrook/deep-neural-networks)方法を学びましょう。

---


*ご質問やご意見がありましたら、[コースディスカッションフォーラム](https://www.kaggle.com/learn/intro-to-deep-learning/discussion)にアクセスして、他の学習者とチャットしてください。*