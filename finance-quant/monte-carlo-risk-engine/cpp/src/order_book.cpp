#include "order_book.hpp"

#include <algorithm>
#include <stdexcept>

namespace mcrisk::lob {

OrderBook::OrderBook(int n_ticks) : n_(n_ticks) {
    if (n_ticks < 2) throw std::invalid_argument("the tick grid needs at least 2 prices");
    for (int s = 0; s < 2; ++s) {
        lv_[s].resize(n_);
        vol_[s].assign(n_, 0);
    }
    best_[BID] = -1;
    best_[ASK] = n_;
    loc_.push_back({0, 0, false});
}

std::int64_t OrderBook::new_id() {
    loc_.push_back({0, 0, false});
    return static_cast<std::int64_t>(loc_.size()) - 1;
}

void OrderBook::check_price(int price) const {
    if (price < 0 || price >= n_) throw std::out_of_range("price outside the tick grid");
}

std::int64_t OrderBook::match(int taker_side, std::int64_t qty, int limit_price,
                              std::int64_t taker_id, int owner) {
    const int maker = 1 - taker_side;
    std::int64_t filled = 0;
    auto crosses = [&]() {
        return taker_side == BID ? (best_[ASK] < n_ && best_[ASK] <= limit_price)
                                 : (best_[BID] >= 0 && best_[BID] >= limit_price);
    };
    while (qty > 0 && crosses()) {
        const int p = best_[maker];
        auto& level = lv_[maker][p];
        while (qty > 0 && !level.empty()) {
            Order& o = level.front();
            const std::int64_t q = std::min(qty, o.qty);
            fills_.push_back({o.id, taker_id, p, q, taker_side, o.owner, owner});
            o.qty -= q;
            qty -= q;
            filled += q;
            vol_[maker][p] -= q;
            total_[maker] -= q;
            if (o.qty == 0) {
                loc_[o.id].live = false;
                level.pop_front();
                --norders_[maker];
            }
        }
        if (level.empty()) fix_best(maker);
    }
    return filled;
}

std::int64_t OrderBook::limit(int side, int price, std::int64_t qty, int owner) {
    check_price(price);
    if (qty <= 0) throw std::invalid_argument("quantity must be positive");
    const std::int64_t id = new_id();
    qty -= match(side, qty, price, id, owner);
    if (qty > 0) {
        lv_[side][price].push_back({id, qty, owner});
        vol_[side][price] += qty;
        total_[side] += qty;
        ++norders_[side];
        loc_[id] = {price, static_cast<std::int8_t>(side), true};
        if (side == BID ? price > best_[BID] : price < best_[ASK]) best_[side] = price;
    }
    return id;
}

std::int64_t OrderBook::market(int side, std::int64_t qty, int owner) {
    if (qty <= 0) throw std::invalid_argument("quantity must be positive");
    const std::int64_t id = new_id();
    return match(side, qty, side == BID ? n_ - 1 : 0, id, owner);
}

void OrderBook::erase_at(int side, int price, std::size_t k) {
    auto& level = lv_[side][price];
    const Order o = level[k];
    level.erase(level.begin() + static_cast<std::ptrdiff_t>(k));
    vol_[side][price] -= o.qty;
    total_[side] -= o.qty;
    --norders_[side];
    loc_[o.id].live = false;
    if (level.empty() && price == best_[side]) fix_best(side);
}

bool OrderBook::cancel(std::int64_t id) {
    if (id <= 0 || id >= static_cast<std::int64_t>(loc_.size()) || !loc_[id].live) return false;
    const Loc l = loc_[id];
    auto& level = lv_[l.side][l.price];
    for (std::size_t k = 0; k < level.size(); ++k) {
        if (level[k].id == id) {
            erase_at(l.side, l.price, k);
            return true;
        }
    }
    throw std::logic_error("order index out of sync with the book");
}

std::int64_t OrderBook::cancel_at(int side, int price, std::size_t k) {
    check_price(price);
    auto& level = lv_[side][price];
    if (k >= level.size()) throw std::out_of_range("no such order in the level");
    const std::int64_t id = level[k].id;
    erase_at(side, price, k);
    return id;
}

void OrderBook::fix_best(int side) {
    if (norders_[side] == 0) {
        best_[side] = side == BID ? -1 : n_;
        return;
    }
    int p = best_[side];
    if (side == BID) {
        while (p >= 0 && lv_[BID][p].empty()) --p;
    } else {
        while (p < n_ && lv_[ASK][p].empty()) ++p;
    }
    best_[side] = p;
}

std::int64_t OrderBook::volume(int side, int price) const {
    return (price < 0 || price >= n_) ? 0 : vol_[side][price];
}

std::size_t OrderBook::count(int side, int price) const {
    return (price < 0 || price >= n_) ? 0 : lv_[side][price].size();
}

bool OrderBook::is_live(std::int64_t id) const {
    return id > 0 && id < static_cast<std::int64_t>(loc_.size()) && loc_[id].live;
}

bool OrderBook::check_invariants() const {
    for (int s = 0; s < 2; ++s) {
        std::int64_t tot = 0;
        std::size_t cnt = 0;
        int best = s == BID ? -1 : n_;
        for (int p = 0; p < n_; ++p) {
            std::int64_t v = 0;
            for (const Order& o : lv_[s][p]) {
                if (o.qty <= 0) return false;
                const Loc& l = loc_[o.id];
                if (!l.live || l.price != p || l.side != s) return false;
                v += o.qty;
            }
            if (v != vol_[s][p]) return false;
            tot += v;
            cnt += lv_[s][p].size();
            if (!lv_[s][p].empty()) best = s == BID ? std::max(best, p) : std::min(best, p);
        }
        if (tot != total_[s] || cnt != norders_[s] || best != best_[s]) return false;
    }
    return best_[BID] < best_[ASK];     // the book is never crossed
}

}  // namespace mcrisk::lob
