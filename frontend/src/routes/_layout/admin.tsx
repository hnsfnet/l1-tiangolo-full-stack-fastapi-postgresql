import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  RefreshCw,
  Search,
  Users,
} from "lucide-react"
import { useEffect, useState } from "react"
import { z } from "zod"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"

const PER_PAGE_OPTIONS = [5, 10, 25, 50] as const
const DEFAULT_PER_PAGE = 10

const usersSearchSchema = z.object({
  page: z.coerce.number().int().min(1).catch(1),
  pageSize: z.coerce
    .number()
    .int()
    .refine((value) =>
      PER_PAGE_OPTIONS.includes(value as (typeof PER_PAGE_OPTIONS)[number]),
    )
    .catch(DEFAULT_PER_PAGE),
  q: z.string().catch(""),
  status: z.enum(["all", "active", "inactive"]).catch("all"),
  role: z.enum(["all", "superuser", "user"]).catch("all"),
  sort: z.enum(["created_at", "email"]).catch("created_at"),
  order: z.enum(["asc", "desc"]).catch("desc"),
})

type UsersSearch = z.infer<typeof usersSearchSchema>

function getUsersQueryOptions(search: UsersSearch) {
  return {
    queryKey: ["users", search] as const,
    queryFn: () =>
      UsersService.readUsers({
        skip: (search.page - 1) * search.pageSize,
        limit: search.pageSize,
        q: search.q.trim() || undefined,
        isActive: search.status === "all" ? undefined : search.status === "active",
        isSuperuser: search.role === "all" ? undefined : search.role === "superuser",
        sort: search.sort,
        order: search.order,
      }),
    placeholderData: keepPreviousData,
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  validateSearch: usersSearchSchema,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Admin - FastAPI Template",
      },
    ],
  }),
})

function UsersTable({
  data,
  isFetchingNext,
}: {
  data: UserTableData[]
  isFetchingNext: boolean
}) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div
      className={cn(
        "transition-opacity",
        isFetchingNext && "pointer-events-none opacity-60",
      )}
    >
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function UsersContent() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()

  const { data, isLoading, isError, error, refetch, isPlaceholderData } =
    useQuery(getUsersQueryOptions(search))

  const [searchInput, setSearchInput] = useState(search.q)

  // Keep the input in sync when the URL changes externally (e.g. back/forward).
  useEffect(() => {
    setSearchInput(search.q)
  }, [search.q])

  // Debounce typing into the search box before writing it to the URL.
  useEffect(() => {
    if (searchInput === search.q) return
    const handle = setTimeout(() => {
      navigate({
        search: (prev) => ({ ...prev, q: searchInput, page: 1 }),
      })
    }, 300)
    return () => clearTimeout(handle)
  }, [searchInput, search.q, navigate])

  const count = data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(count / search.pageSize))

  // If filters shrink the result set below the current page, clamp back in range.
  useEffect(() => {
    if (isPlaceholderData) return
    if (count > 0 && search.page > totalPages) {
      navigate({ search: (prev) => ({ ...prev, page: totalPages }) })
    }
  }, [count, totalPages, search.page, isPlaceholderData, navigate])

  const updateFilter = (updates: Partial<UsersSearch>) => {
    navigate({ search: (prev) => ({ ...prev, ...updates, page: 1 }) })
  }

  const goToPage = (page: number) => {
    navigate({ search: (prev) => ({ ...prev, page }) })
  }

  const users = data?.data ?? []
  const tableData: UserTableData[] = users.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  const hasActiveFilters =
    search.q.trim() !== "" || search.status !== "all" || search.role !== "all"
  const sortValue = `${search.sort}:${search.order}`

  const firstRow = count === 0 ? 0 : (search.page - 1) * search.pageSize + 1
  const lastRow = Math.min(search.page * search.pageSize, count)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="user-search-input"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search by name or email"
            className="pl-8"
          />
        </div>

        <Select
          value={search.status}
          onValueChange={(value) =>
            updateFilter({ status: value as UsersSearch["status"] })
          }
        >
          <SelectTrigger
            data-testid="user-status-filter"
            className="w-full sm:w-[150px]"
          >
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={search.role}
          onValueChange={(value) =>
            updateFilter({ role: value as UsersSearch["role"] })
          }
        >
          <SelectTrigger
            data-testid="user-role-filter"
            className="w-full sm:w-[150px]"
          >
            <SelectValue placeholder="Role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            <SelectItem value="superuser">Superuser</SelectItem>
            <SelectItem value="user">User</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={sortValue}
          onValueChange={(value) => {
            const [sort, order] = value.split(":") as [
              UsersSearch["sort"],
              UsersSearch["order"],
            ]
            updateFilter({ sort, order })
          }}
        >
          <SelectTrigger
            data-testid="user-sort"
            className="w-full sm:w-[170px]"
          >
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created_at:desc">Newest first</SelectItem>
            <SelectItem value="created_at:asc">Oldest first</SelectItem>
            <SelectItem value="email:asc">Email (A-Z)</SelectItem>
            <SelectItem value="email:desc">Email (Z-A)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <PendingUsers />
      ) : isError ? (
        <Alert variant="destructive">
          <AlertTitle>Unable to load users</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            <span>
              {error instanceof Error
                ? error.message
                : "Something went wrong while fetching users."}
            </span>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="size-4" />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : tableData.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <div className="mb-4 rounded-full bg-muted p-4">
            <Users className="size-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">
            {hasActiveFilters ? "No users match your filters" : "No users yet"}
          </h3>
          <p className="text-muted-foreground">
            {hasActiveFilters
              ? "Try adjusting your search or filters."
              : "Add a new user to get started."}
          </p>
          {hasActiveFilters && (
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() =>
                updateFilter({ q: "", status: "all", role: "all" })
              }
            >
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <UsersTable data={tableData} isFetchingNext={isPlaceholderData} />
      )}

      {!isLoading && !isError && count > 0 && (
        <div className="flex flex-col items-start justify-between gap-4 border-t bg-muted/20 p-4 sm:flex-row sm:items-center">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="text-sm text-muted-foreground">
              Showing{" "}
              <span className="font-medium text-foreground">{firstRow}</span> to{" "}
              <span className="font-medium text-foreground">{lastRow}</span> of{" "}
              <span className="font-medium text-foreground">{count}</span> users
            </div>
            <div className="flex items-center gap-x-2">
              <p className="text-sm text-muted-foreground">Rows per page</p>
              <Select
                value={`${search.pageSize}`}
                onValueChange={(value) =>
                  updateFilter({ pageSize: Number(value) })
                }
              >
                <SelectTrigger className="h-8 w-[70px]">
                  <SelectValue placeholder={search.pageSize} />
                </SelectTrigger>
                <SelectContent side="top">
                  {PER_PAGE_OPTIONS.map((pageSize) => (
                    <SelectItem key={pageSize} value={`${pageSize}`}>
                      {pageSize}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center gap-x-6">
            <div className="flex items-center gap-x-1 text-sm text-muted-foreground">
              <span>Page</span>
              <span className="font-medium text-foreground">{search.page}</span>
              <span>of</span>
              <span className="font-medium text-foreground">{totalPages}</span>
            </div>

            <div className="flex items-center gap-x-1">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(1)}
                disabled={search.page <= 1}
              >
                <span className="sr-only">Go to first page</span>
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(search.page - 1)}
                disabled={search.page <= 1}
              >
                <span className="sr-only">Go to previous page</span>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(search.page + 1)}
                disabled={search.page >= totalPages}
              >
                <span className="sr-only">Go to next page</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(totalPages)}
                disabled={search.page >= totalPages}
              >
                <span className="sr-only">Go to last page</span>
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Admin() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">
            Manage user accounts and permissions
          </p>
        </div>
        <AddUser />
      </div>
      <UsersContent />
    </div>
  )
}
