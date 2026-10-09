"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bookClass,
  cancelBooking,
  createClassSchedule,
  listClassBookings,
  listClassSchedules,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ClassesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [capacity, setCapacity] = useState("10");
  const [memberIdToBook, setMemberIdToBook] = useState("");
  const [selectedClass, setSelectedClass] = useState<string | null>(null);

  const classes = useQuery({ queryKey: ["coaching", "classes"], queryFn: listClassSchedules });
  const classList = Array.isArray(classes.data) ? classes.data : classes.data?.results ?? [];

  const bookings = useQuery({
    queryKey: ["coaching", "bookings", selectedClass],
    queryFn: () => listClassBookings(selectedClass ?? undefined),
    enabled: Boolean(selectedClass),
  });
  const bookingList = Array.isArray(bookings.data) ? bookings.data : bookings.data?.results ?? [];

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["coaching", "classes"] });
    queryClient.invalidateQueries({ queryKey: ["coaching", "bookings"] });
  }

  async function createClass(e: React.FormEvent) {
    e.preventDefault();
    await createClassSchedule({ name, starts_at: startsAt, capacity: Number(capacity) });
    setName("");
    setStartsAt("");
    refresh();
  }

  async function book() {
    if (!selectedClass || !memberIdToBook) return;
    await bookClass({ class_schedule: selectedClass, member: memberIdToBook });
    setMemberIdToBook("");
    refresh();
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Classes</h1>

      <form onSubmit={createClass} className="flex flex-wrap items-end gap-3 rounded border p-3">
        <div className="space-y-1">
          <Label htmlFor="class-name">Name</Label>
          <Input id="class-name" value={name} onChange={(e) => setName(e.target.value)} className="w-40" required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="class-starts">Starts at</Label>
          <Input
            id="class-starts"
            type="datetime-local"
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="class-capacity">Capacity</Label>
          <Input
            id="class-capacity"
            type="number"
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
            className="w-20"
          />
        </div>
        <Button type="submit">Create class</Button>
      </form>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <ul className="space-y-2">
          {classList.map((cls) => (
            <li
              key={cls.id}
              className={`cursor-pointer rounded border px-3 py-2 text-sm ${selectedClass === cls.id ? "border-primary" : ""}`}
              onClick={() => setSelectedClass(cls.id)}
            >
              <p className="font-medium">{cls.name}</p>
              <p className="opacity-60">
                {new Date(cls.starts_at).toLocaleString()} &middot; {cls.booked_count}/{cls.capacity}
              </p>
            </li>
          ))}
          {classList.length === 0 && <li className="text-sm opacity-60">No classes scheduled.</li>}
        </ul>

        {selectedClass && (
          <div className="space-y-3 rounded border p-3">
            <h2 className="text-sm font-medium">Bookings</h2>
            <div className="flex gap-2">
              <Input
                placeholder="Member ID"
                value={memberIdToBook}
                onChange={(e) => setMemberIdToBook(e.target.value)}
                className="h-8"
              />
              <Button size="sm" onClick={book}>
                Book
              </Button>
            </div>
            <ul className="space-y-1 text-sm">
              {bookingList.map((booking) => (
                <li key={booking.id} className="flex items-center justify-between rounded border px-2 py-1">
                  <span>
                    {booking.member_name} &middot; <span className="capitalize">{booking.status}</span>
                  </span>
                  {booking.status !== "cancelled" && (
                    <button
                      onClick={async () => {
                        await cancelBooking(booking.id);
                        refresh();
                      }}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Cancel
                    </button>
                  )}
                </li>
              ))}
              {bookingList.length === 0 && <li className="text-sm opacity-60">No bookings yet.</li>}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
