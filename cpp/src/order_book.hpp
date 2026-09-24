#pragma once
// Price-time priority limit order book on an integer tick grid.
//
// * limit orders match against the opposite side up to their limit price,
//   the remainder rests at the back of its price level (FIFO)
// * market orders walk the opposite side until filled or the side is empty
// * cancellations by order id; each id maps to its (side, price) in O(1)
//
// Every execution is appended to fills() with maker and taker ids.

#include <cstdint>
#include <deque>
#include <vector>

namespace mcrisk::lob {

constexpr int BID = 0;   // buy side / buy taker
constexpr int ASK = 1;   // sell side / sell taker

struct Order {
    std::int64_t id;
    std::int64_t qty;
    std::int32_t owner;
};

struct Fill {
    std::int64_t maker_id;
    std::int64_t taker_id;
    std::int32_t price;
    std::int64_t qty;
    std::int32_t taker_side;     // BID = buy taker (lifts asks), ASK = sell taker
    std::int32_t maker_owner;
    std::int32_t taker_owner;
};

class OrderBook {
  public:
    explicit OrderBook(int n_ticks);

    int n_ticks() const { return n_; }
    // Returns the order id; the order may be (partly) filled on arrival.
    std::int64_t limit(int side, int price, std::int64_t qty, int owner = 0);
    // Returns the quantity filled.
    std::int64_t market(int side, std::int64_t qty, int owner = 0);
    bool cancel(std::int64_t id);
    // Cancels the k-th order (FIFO position) of a level; returns its id.
    std::int64_t cancel_at(int side, int price, std::size_t k);

    int best_bid() const { return best_[BID]; }     // -1 when the bid side is empty
    int best_ask() const { return best_[ASK]; }     // n_ticks when the ask side is empty
    std::int64_t volume(int side, int price) const;
    std::size_t count(int side, int price) const;
    std::int64_t total_volume(int side) const { return total_[side]; }
    std::size_t total_orders(int side) const { return norders_[side]; }
    bool is_live(std::int64_t id) const;

    std::vector<Fill>& fills() { return fills_; }
    const std::vector<Fill>& fills() const { return fills_; }
    // Full consistency check (volumes, counts, best prices, index); for tests.
    bool check_invariants() const;

  private:
    struct Loc {
        std::int32_t price;
        std::int8_t side;
        bool live;
    };
    int n_;
    std::vector<std::deque<Order>> lv_[2];
    std::vector<std::int64_t> vol_[2];
    std::int64_t total_[2] = {0, 0};
    std::size_t norders_[2] = {0, 0};
    int best_[2];
    std::vector<Loc> loc_;       // indexed by order id (id 0 unused)
    std::vector<Fill> fills_;

    std::int64_t new_id();
    void check_price(int price) const;
    std::int64_t match(int taker_side, std::int64_t qty, int limit_price,
                       std::int64_t taker_id, int owner);
    void erase_at(int side, int price, std::size_t k);
    void fix_best(int side);
};

}  // namespace mcrisk::lob
