import random
from reconchess import *
from sortedcontainers import SortedList
from multiprocessing import Pool, TimeoutError

def true_eval(color, board) -> float:
	num = 0
	for square, piece in board.piece_map().items():
		mult = 1
		val = 0
		if piece.color != color:
			mult = -1
		if piece.piece_type == chess.PAWN:
			val = 1
		elif piece.piece_type == chess.KNIGHT:
			val = 10
		elif piece.piece_type == chess.BISHOP:
			val = 10
		elif piece.piece_type == chess.ROOK:
			val = 10
		elif piece.piece_type == chess.QUEEN:
			val = 20
		elif piece.piece_type == chess.KING:
			val = 1000
			attackers = board.attackers(not piece.color, square)
			if len(attackers) != 0:
				num = num - mult * 500
				if piece.color == color:
					num = num - 500
		num = num + mult * val
	return num/2

def eval_board(color, board) -> float:
	trials = 5
	trialDepth = 3
	score = 0
	inp = []
	for i in range(trials):
		tBoard = board.copy()
		won = False
		for j in range(trialDepth):
			if not board.king(color):
				score = score - 1000
				won = True
				break

			if not board.king(not color):
				score = score + 1000
				won = True
				break

			potMoves = []
			for mv in board.pseudo_legal_moves:
				potMoves.append(mv)
			if len(potMoves) == 0:
				break
			m = random.choice(potMoves)
			board.push(m)
		if not won:
			num = true_eval(color, board)
			score = score + num
			
	return score / trials

def alphabeta(inp) -> float:
	(color, board, depth, alpha, beta, maximizing) = inp
	terminal = False
	tMove = None
	mod = 0
	e_king_square = board.king(not color)
	if not e_king_square:
		terminal = True
		mod = 1000
	elif maximizing:
		attackers = board.attackers(color, e_king_square)
		if attackers:
			mod = 1000
			terminal = True
			tMove = chess.Move(attackers.pop(), e_king_square)
	m_king_square = board.king(color)
	if not m_king_square:
		terminal = True
		mod = -1000
	elif not maximizing:
		attackers = board.attackers(not color, m_king_square)
		if attackers:
			mod = -1000
			terminal = True
			tMove = chess.Move(attackers.pop(), m_king_square)
	if depth == 0 or terminal:
		return (eval_board(color, board) + mod, tMove, None)

	if maximizing:
		if board.turn != color:
			board.push(chess.Move.null())
		val = float("-inf")
		bM = []
		for mv in board.legal_moves:
			tB = board.copy()
			tB.push(mv)
			(v, m, r) = alphabeta((color, tB, depth - 1, alpha, beta, False))

			if v > val:
				bM = [(mv, m)]
				val = v
			elif v == val:
				bM.append((mv,m))

			alpha = max(alpha, val)
			if alpha >= beta:
				break
		if len(bM) == 0:
			return (val, None, None)
		else:
			(mov, resp) = random.choice(bM)
			return (val, mov, resp)
	else:
		if board.turn == color:
			board.push(chess.Move.null())
		val = float("inf")
		bM = []
		res = []
		for mv in board.legal_moves:
			tB = board.copy()
			tB.push(mv)
			(v, m, r) = alphabeta((color, tB, depth - 1, alpha, beta, True))

			if v < val:
				bM = [(mv, m)]
				val = v
			elif v == val:
				bM.append((mv,m))

			beta = min(beta, val)
			if alpha >= beta:
				break
		if len(bM) == 0:
			return (val, None, None)
		else:
			(mov, resp) = random.choice(bM)
			return (val, mov, resp)
def abprocess(inp) -> float:
	(color, boards, depth) = inp
	alpha = float("-inf")
	beta = float("inf")
	maximizing = True
	mov = []
	for board in boards:
		(v, m, r) = alphabeta((color, board, depth, alpha, beta, maximizing))
		if v < beta and m is not None:
			mov = [(m,r)]
			beta = v
		if v == beta:
			mov.append((m,r))
	if len(mov) == 0:
		return (beta, None, None)
	else:
		(m, r) = random.choice(mov)
		return (beta, m, r)

def partition (list_in, n):
    random.shuffle(list_in)
    return [list_in[i::n] for i in range(n)]

class Inference(Player):
	def __init__(self):
		self.color = None
		self.moveNum = 0
		self.approxTime = 900
		self.potBoards = {}
		self.score = 0
		self.expectedScore = 0
		self.numWorkers = 4
		self.pool = Pool(processes=self.numWorkers)

	def advanceBoardsNoTake(self):
		newBoards = {}
		for k in self.potBoards:
			newBoards[k] = 1
			tBoard = chess.Board()
			tBoard.set_fen(k)
			if tBoard.turn == self.color:
				tBoard.push(chess.Move.null())

			for mv in tBoard.pseudo_legal_moves:
				if tBoard.piece_at(mv.to_square) is None:
					ttBoard = tBoard.copy()
					ttBoard.push(mv)
					newBoards[ttBoard.fen()] = 1
		self.potBoards = newBoards

	def advanceBoardsTaken(self, tile):
		newBoards = {}
		for k in self.potBoards:
			tBoard = chess.Board()
			tBoard.set_fen(k)
			if tBoard.turn == self.color:
				tBoard.push(chess.Move.null())
			for mv in tBoard.pseudo_legal_moves:
				if mv.to_square == tile:
					ttBoard = tBoard.copy()
					ttBoard.push(mv)
					newBoards[ttBoard.fen()] = 1
		self.potBoards = newBoards

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.color = color
		self.potBoards[board.fen()] = 1

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		print("")
		if self.moveNum != 0 or self.color == chess.BLACK:
			if captured_my_piece:
				print("Piece taken at ", chess.SQUARE_NAMES[capture_square])
				self.advanceBoardsTaken(capture_square)
			else:
				self.advanceBoardsNoTake()

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:
		bDif = {}
		sqset = chess.SquareSet(chess.BB_ALL)
		for square in sqset:
			bDif[square] = (0, 0, 0, 0, 0, 0, 0)
		for k in self.potBoards:
			tBoard = chess.Board()
			tBoard.set_fen(k)
			for square in sqset:
				p = tBoard.piece_at(square)
				(n, pawn, knight, bishop, rook, queen, king) = bDif[square]
				if p is None:
					n = n + 1
				elif p.piece_type == chess.PAWN:
					pawn = pawn + 1
				elif p.piece_type == chess.KNIGHT:
					knight = knight + 1
				elif p.piece_type == chess.BISHOP:
					bishop = bishop + 1
				elif p.piece_type == chess.ROOK:
					rook = rook + 1
				elif p.piece_type == chess.QUEEN:
					queen = queen + 1
				elif p.piece_type == chess.KING:
					king = king + 1

				bDif[square] = (n, pawn, knight, bishop, rook, queen, king)
		minSq = None
		minNum = 0
		for square in sqset:
			mn = len(self.potBoards) - max(bDif[square])

			if mn > minNum:
				minNum = mn
				minSq = square

		if minSq is None:
			print("No scan needed")
			return None
		else:
			return minSq

	def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
		newBoards = {}
		for k in self.potBoards:
			tBoard = chess.Board()
			tBoard.set_fen(k)
			good = True
			for square, piece in sense_result:
				if tBoard.piece_at(square) is None and piece is not None:
					good = False
					break
				elif tBoard.piece_at(square) is not None and piece is None:
					good = False
					break
				elif tBoard.piece_at(square) is not None and piece is not None:
					if tBoard.piece_at(square).piece_type != piece.piece_type:
						good = False
						break
					if tBoard.piece_at(square).color != piece.color:
						good = False
						break
			if good:
				newBoards[k] = 1
		self.potBoards = newBoards


	def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
		self.approxTime = seconds_left

		alpha = float("-inf")
		beta = float("inf")
		mov = None
		score = 0
		count = 0
		toRun = []
		depth = 0
		if len(self.potBoards) > 50:
			runBoards = random.sample(list(self.potBoards), 50)
			for b in runBoards:
				tBoard = chess.Board()
				tBoard.set_fen(b)
				score = score + true_eval(self.color, tBoard)
				toRun.append(tBoard)
				count = count + 1
				depth = 3
		elif len(self.potBoards) > 8:
			for b in self.potBoards:
				tBoard = chess.Board()
				tBoard.set_fen(b)
				score = score + true_eval(self.color, tBoard)
				toRun.append(tBoard)
				count = count + 1
				depth = 3
		else:
			for b in self.potBoards:
				tBoard = chess.Board()
				tBoard.set_fen(b)
				score = score + true_eval(self.color, tBoard)
				toRun.append(tBoard)
				count = count + 1
				depth = 4
		rB = partition(toRun, self.numWorkers)
		inp = []
		for r in rB:
			inp.append((self.color, r, depth))
		print("Scanning ", len(toRun), "|", len(self.potBoards), " states to a depth of ", depth)
		out = self.pool.imap_unordered(abprocess, inp)
		for o in out:
			(v, m, r) = o
			if v < beta and m is not None:
				beta = v
				mov = m


		if count != 0:
			self.score = score / count
		self.expectedScore = beta

		if mov in move_actions:
			print(mov)
			return mov
		else:
			print("Illegal move requested")
			print(mov)
			return None

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		if captured_opponent_piece:
			print("I killed something")
		newBoards = {}
		for k in self.potBoards:
			tBoard = chess.Board()
			tBoard.set_fen(k)
			if tBoard.turn != self.color:
				tBoard.push(chess.Move.null())

			if taken_move is not None:
				if (captured_opponent_piece == True) and (tBoard.piece_at(capture_square) is not None) and (tBoard.piece_at(capture_square).color != self.color):
					tBoard.push(taken_move)
					newBoards[tBoard.fen()] = 1
				elif (captured_opponent_piece == False) and (tBoard.piece_at(taken_move.to_square) is None):
					tBoard.push(taken_move)
					newBoards[tBoard.fen()] = 1
			elif requested_move is not None:
				if (tBoard.piece_at(requested_move.from_square) is not None) and (tBoard.piece_at(requested_move.from_square).piece_type == chess.PAWN):
					if tBoard.piece_at(requested_move.to_square) is None and (chess.square_file(requested_move.from_square) != chess.square_file(requested_move.to_square)):
						newBoards[k] = 1
					elif (chess.square_file(requested_move.from_square) == chess.square_file(requested_move.to_square)):
						if abs(chess.square_rank(requested_move.from_square) - chess.square_rank(requested_move.to_square)) == 2:
							if tBoard.piece_at(chess.Square(chess.square_file(requested_move.to_square), (chess.square_rank(requested_move.from_square) + chess.square_rank(requested_move.to_square))/2)) is not None:
								newBoards[k] = 1
						else:
							if tBoard.piece_at(requested_move.to_square) is not None:
								newBoards[k] = 1
			else:
				newBoards[k] = 1
		self.potBoards = newBoards

		#if taken_move is not None:
		#	self.board.push(taken_move)
		self.moveNum = self.moveNum + 1

		print("Considering ", len(self.potBoards), " potential board states")
		print ("Inference:\t End move ", self.moveNum, " -- approx ", '{:06.2f}'.format(self.approxTime), " seconds left || Score: ", '{:06.1f}'.format(self.score), "Expected Score: ", '{:06.1f}'.format(self.expectedScore))

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		pass
