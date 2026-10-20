"""
analysis.py
Analyses data/books_clean.csv (created by scraper.py), prints the results
and saves three charts in the "charts" folder.

Run with:  python analysis.py
"""

import os
import sys

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

DATA_FILE = os.path.join("data", "books_clean.csv")
CHART_FOLDER = "charts"


def load_data():
    """Load the cleaned dataset, with a helpful message if it is missing."""
    if not os.path.exists(DATA_FILE):
        print(f"{DATA_FILE} was not found. Run 'python scraper.py' first.")
        sys.exit(1)
    return pd.read_csv(DATA_FILE)


def category_table(df):
    """Book count, average price and average rating for each category."""
    return (
        df.groupby("category")
        .agg(book_count=("title", "count"),
             avg_price=("price_gbp", "mean"),
             avg_rating=("rating", "mean"))
        .round(2)
        .sort_values("avg_price", ascending=False)
    )


def print_analysis(df):
    """Print the main statistics and tables."""
    print("=" * 60)
    print("PRICE ANALYSIS")
    print("=" * 60)
    print(f"Total books: {len(df)}")
    print(f"Average price: £{df['price_gbp'].mean():.2f}")
    print(f"Median price:  £{df['price_gbp'].median():.2f}")
    print(f"Cheapest price: £{df['price_gbp'].min():.2f}")
    print(f"Highest price:  £{df['price_gbp'].max():.2f}")

    print("\n5 cheapest books:")
    print(df.nsmallest(5, "price_gbp")[["title", "category", "price_gbp", "rating"]].to_string(index=False))
    print("\n5 most expensive books:")
    print(df.nlargest(5, "price_gbp")[["title", "category", "price_gbp", "rating"]].to_string(index=False))

    print("\n" + "=" * 60)
    print("RATING ANALYSIS")
    print("=" * 60)
    print("Number of books per star rating:")
    print(df["rating"].value_counts().sort_index().to_string())
    print("\nAverage price per star rating (£):")
    print(df.groupby("rating")["price_gbp"].mean().round(2).to_string())
    print(f"\nCorrelation between price and rating: {df['price_gbp'].corr(df['rating']):.2f}")

    print("\n" + "=" * 60)
    print("CATEGORY ANALYSIS")
    print("=" * 60)
    stats = category_table(df)
    print(f"Number of categories: {len(stats)}")
    print("\nTop 10 categories by average price:")
    print(stats.head(10).to_string())
    print("\nBottom 5 categories by average price:")
    print(stats.tail(5).to_string())
    print("\nTop 5 categories by number of books:")
    print(stats.sort_values("book_count", ascending=False).head(5).to_string())

    print("\n" + "=" * 60)
    print("AVAILABILITY ANALYSIS")
    print("=" * 60)
    print("Availability text counts:")
    print(df["availability"].value_counts().to_string())
    print(f"\nBooks marked in stock: {df['in_stock'].sum()} of {len(df)}")


def save_charts(df):
    """Create and save three charts."""
    os.makedirs(CHART_FOLDER, exist_ok=True)
    sns.set_theme(style="whitegrid")

    # Chart 1: number of books for each star rating
    rating_counts = df["rating"].value_counts().sort_index()
    plt.figure(figsize=(8, 5))
    ax = sns.barplot(x=rating_counts.index, y=rating_counts.values, color="steelblue")
    ax.set_title("Number of Books by Star Rating")
    ax.set_xlabel("Star Rating (1 = lowest, 5 = highest)")
    ax.set_ylabel("Number of Books")
    for container in ax.containers:
        ax.bar_label(container)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_FOLDER, "01_rating_distribution.png"), dpi=150)
    plt.close()

    # Chart 2: top 10 categories by average price
    top_categories = category_table(df)["avg_price"].head(10)
    plt.figure(figsize=(9, 6))
    ax = sns.barplot(x=top_categories.values, y=top_categories.index,
                     orient="h", color="darkorange")
    ax.set_title("Top 10 Categories by Average Book Price")
    ax.set_xlabel("Average Price (£)")
    ax.set_ylabel("Category")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.2f")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_FOLDER, "02_top_categories_avg_price.png"), dpi=150)
    plt.close()

    # Chart 3: how book prices are spread
    plt.figure(figsize=(8, 5))
    ax = sns.histplot(df["price_gbp"], bins=20, color="seagreen")
    ax.set_title("Distribution of Book Prices")
    ax.set_xlabel("Price (£)")
    ax.set_ylabel("Number of Books")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_FOLDER, "03_price_distribution.png"), dpi=150)
    plt.close()

    print("\nCharts saved in the 'charts' folder:", sorted(os.listdir(CHART_FOLDER)))


def main():
    df = load_data()
    print_analysis(df)
    save_charts(df)


if __name__ == "__main__":
    main()
