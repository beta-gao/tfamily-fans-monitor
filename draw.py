import pandas as pd
import matplotlib.pyplot as plt

CSV_FILE = "tf_family_fans_multi.csv"
OUTPUT_FILE = "fans_relative_trend.png"
EXCLUDE_TAGS = {"官俊臣"}

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 读取数据
df = pd.read_csv(CSV_FILE)

# 清理与转换
df["time"] = pd.to_datetime(df["time"])
df["fans_num"] = pd.to_numeric(df["fans_num"], errors="coerce")
df = df.dropna(subset=["time", "tag", "fans_num"])

# 排序
df = df.sort_values(["tag", "time"])

# 排除不想看的 tag
df = df[~df["tag"].isin(EXCLUDE_TAGS)]

# 只保留每个 tag 至少有 2 个点的数据
counts = df.groupby("tag").size()
valid_tags = counts[counts >= 2].index
df = df[df["tag"].isin(valid_tags)]

# 计算“相对增长量” = 当前粉丝 - 该 tag 的起始粉丝
df["relative_growth"] = df.groupby("tag")["fans_num"].transform(lambda s: s - s.iloc[0])

# 画图
plt.figure(figsize=(13, 7))

for tag in df["tag"].unique():
    sub_df = df[df["tag"] == tag].copy()
    start_fans = int(sub_df["fans_num"].iloc[0])
    current_fans = int(sub_df["fans_num"].iloc[-1])
    total_growth = int(sub_df["relative_growth"].iloc[-1])

    label = (
        tag
        + " | start=" + format(start_fans, ",")
        + " | current=" + format(current_fans, ",")
        + " | +" + format(total_growth, ",")
    )

    plt.plot(
        sub_df["time"],
        sub_df["relative_growth"],
        marker="o",
        linewidth=2,
        markersize=4,
        label=label
    )

# 美化
plt.title(" ")
plt.xlabel("Time")
plt.ylabel("Growth Since Start")
plt.xticks(rotation=45)
plt.legend(fontsize=9)
plt.grid(True, alpha=0.3)
plt.tight_layout()

# 保存和显示
plt.savefig(OUTPUT_FILE, dpi=200)
print("图已保存为:", OUTPUT_FILE)

CSV_FILE = "tf_family_fans_multi.csv"
OUTPUT_FILE = "fans_current_bar.png"
EXCLUDE_TAGS = {"官俊臣"}

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv(CSV_FILE)
df["time"] = pd.to_datetime(df["time"])
df["fans_num"] = pd.to_numeric(df["fans_num"], errors="coerce")
df = df.dropna(subset=["time", "tag", "fans_num"])
df = df[~df["tag"].isin(EXCLUDE_TAGS)]
df = df.sort_values(["tag", "time"])

latest_df = df.groupby("tag", as_index=False).tail(1).copy()
latest_df = latest_df.sort_values("fans_num", ascending=True)

plt.figure(figsize=(10, 6))
plt.barh(latest_df["tag"], latest_df["fans_num"])
plt.title("Current Fans by Tag")
plt.xlabel("Current Fans")
plt.ylabel("Tag")
plt.tight_layout()

plt.savefig(OUTPUT_FILE, dpi=200)

print("图已保存为:", OUTPUT_FILE)